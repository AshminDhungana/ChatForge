from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from openai import AuthenticationError

from backend.config import API_KEY, API_BASE, MODEL

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Circuit-breaker states
# ---------------------------------------------------------------------------

class CircuitState(Enum):
    CLOSED    = "closed"
    HALF_OPEN = "half_open"
    OPEN      = "open"


# ---------------------------------------------------------------------------
# Shared state — ALL mutations must hold _lock
# ---------------------------------------------------------------------------

_state: CircuitState        = CircuitState.CLOSED
_failures: int              = 0
_last_opened_at: datetime | None = None
_lock: asyncio.Lock         = asyncio.Lock()

# Signals the recovery loop to wake up. Set when circuit opens; cleared
# after a successful probe closes it again.
_tripped: asyncio.Event     = asyncio.Event()

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

MAX_FAILURES   = 3    # consecutive failures before opening
BASE_INTERVAL  = 30   # seconds — first probe delay
MAX_INTERVAL   = 300  # seconds — cap on backoff (5 min)


# ---------------------------------------------------------------------------
# Public state accessors (async-safe)
# ---------------------------------------------------------------------------

async def get_circuit_state() -> CircuitState:
    """Return the current circuit state (thread-safe read)."""
    async with _lock:
        return _state


async def is_available() -> bool:
    """Return True when the circuit is CLOSED (normal operation)."""
    return await get_circuit_state() == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# State transition helpers — all hold _lock internally
# ---------------------------------------------------------------------------

async def record_failure(exc: Exception | None = None) -> None:
    """
    Record one failed AI request.

    If exc is an AuthenticationError the circuit is permanently opened and
    the recovery loop is NOT started — a bad API key won't fix itself.
    For all other exceptions consecutive-failure counting applies.
    """
    global _state, _failures, _last_opened_at

    # --- Permanent failure: bad credentials ---
    if isinstance(exc, AuthenticationError):
        async with _lock:
            _state = CircuitState.OPEN
            _last_opened_at = datetime.now(timezone.utc)
        logger.error(
            "AI provider returned AuthenticationError. "
            "Circuit permanently OPEN — check API_KEY."
        )
        # Do NOT set _tripped; the recovery loop cannot fix auth errors.
        return

    # --- Transient failure: count toward threshold ---
    async with _lock:
        _failures += 1
        logger.warning(
            "AI failure recorded (%d/%d).", _failures, MAX_FAILURES
        )
        if _failures >= MAX_FAILURES and _state == CircuitState.CLOSED:
            _state = CircuitState.OPEN
            _last_opened_at = datetime.now(timezone.utc)
            logger.warning("Circuit OPEN — switching to fallback mode.")

    if _failures >= MAX_FAILURES:
        _tripped.set()   # wake recovery loop (safe to call outside lock)


async def record_success() -> None:
    """
    Record a successful AI request.

    Resets the failure counter. If the circuit was HALF_OPEN the probe
    succeeded and the circuit transitions back to CLOSED.
    """
    global _state, _failures

    async with _lock:
        previously = _state
        _failures = 0
        if _state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
            _state = CircuitState.CLOSED
            logger.info("Circuit CLOSED — AI provider recovered.")

    if previously == CircuitState.HALF_OPEN:
        _tripped.clear()   # stop recovery loop from looping again


# ---------------------------------------------------------------------------
# Health probe
# ---------------------------------------------------------------------------

def _build_test_llm() -> ChatOpenAI:
    """Lightweight LLM instance used only for health probes."""
    return ChatOpenAI(
        openai_api_key=API_KEY,
        openai_api_base=API_BASE or None,
        model_name=MODEL,
        max_tokens=5,
    )


async def test_ai_connection() -> None:
    """
    Send a minimal prompt to verify AI connectivity.

    Raises the underlying exception on failure so callers can inspect
    the exception type (e.g. AuthenticationError vs network error).
    """
    if not API_KEY:
        raise RuntimeError("API_KEY not configured")

    llm = _build_test_llm()
    await llm.ainvoke([HumanMessage(content="ping")])


# ---------------------------------------------------------------------------
# Background recovery loop
# ---------------------------------------------------------------------------

async def recovery_loop() -> None:
    """
    Background task that probes the AI provider when the circuit is OPEN.

    Design:
    - Sleeps indefinitely while the circuit is CLOSED (_tripped not set).
    - Wakes when record_failure() opens the circuit and sets _tripped.
    - Waits BASE_INTERVAL * 2^attempt seconds (capped at MAX_INTERVAL).
    - Transitions to HALF_OPEN and attempts a single probe.
      - Probe success  → record_success() closes the circuit, loop resets.
      - Probe failure  → back to OPEN, attempt counter incremented.
    - AuthenticationError is re-raised immediately; the loop exits because
      a bad key cannot be fixed by waiting.
    """
    attempt = 0

    while True:
        # Block here while the circuit is healthy.
        await _tripped.wait()

        interval = min(BASE_INTERVAL * (2 ** attempt), MAX_INTERVAL)
        logger.info(
            "Recovery loop: circuit OPEN (attempt %d). "
            "Probing AI in %ds.", attempt, interval
        )
        await asyncio.sleep(interval)

        # Re-check; the circuit may have been manually reset externally.
        async with _lock:
            current = _state

        if current != CircuitState.OPEN:
            # Already recovered or reset externally — go back to sleep.
            _tripped.clear()
            attempt = 0
            continue

        # Transition to HALF_OPEN for the probe.
        async with _lock:
            _state = CircuitState.HALF_OPEN
        logger.info("Circuit HALF_OPEN — sending probe request.")

        try:
            await test_ai_connection()
            # Probe succeeded — record_success() will close the circuit
            # and clear _tripped.
            await record_success()
            attempt = 0
            logger.info("Probe succeeded. Circuit CLOSED.")

        except AuthenticationError as exc:
            # Permanent failure — re-open the circuit and stop retrying.
            await record_failure(exc)
            logger.error(
                "Probe returned AuthenticationError. "
                "Recovery loop exiting — manual intervention required."
            )
            return   # exit the task entirely

        except Exception:
            # Transient probe failure — back to OPEN and wait longer.
            async with _lock:
                _state = CircuitState.OPEN
            attempt += 1
            next_interval = min(BASE_INTERVAL * (2 ** attempt), MAX_INTERVAL)
            logger.warning(
                "Probe failed (attempt %d). Next probe in %ds.",
                attempt, next_interval
            )
            # _tripped is still set, so the loop will iterate again.


# ---------------------------------------------------------------------------
# Legacy compatibility shims
# ---------------------------------------------------------------------------
# These let existing call-sites in chat.py keep working without changes
# while the internals have been upgraded to the three-state model.

def mark_ai_down() -> None:
    """Synchronous shim — prefer the async record_failure() instead."""
    global _state, _last_opened_at
    _state = CircuitState.OPEN
    _last_opened_at = datetime.now(timezone.utc)
    _tripped.set()
    logger.warning("AI provider marked down (sync shim).")


def mark_ai_up() -> None:
    """Synchronous shim — prefer the async record_success() instead."""
    global _state, _failures
    _state = CircuitState.CLOSED
    _failures = 0
    _tripped.clear()
    logger.info("AI provider marked up (sync shim).")


# ---------------------------------------------------------------------------
# Convenience property for main.py /api/v1/ai-status endpoint
# ---------------------------------------------------------------------------

def get_status_dict() -> dict:
    """
    Return a snapshot of circuit-breaker state for the status endpoint.

    Note: reads globals without acquiring the lock — acceptable for a
    monitoring endpoint where eventual consistency is fine.
    """
    return {
        "state":    _state.value,
        "available": _state == CircuitState.CLOSED,
        "mode":     "ai" if _state == CircuitState.CLOSED else "fallback",
        "failures": _failures,
        "last_opened_at": _last_opened_at.isoformat() if _last_opened_at else None,
    }