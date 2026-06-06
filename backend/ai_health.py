import asyncio
import logging
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from backend.config import API_KEY, API_BASE, MODEL

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# AI Health state
# ---------------------------------------------------------------------------

AI_AVAILABLE = True
CONSECUTIVE_FAILURES = 0
MAX_FAILURES = 3
LAST_FAILURE = None
RECOVERY_CHECK_INTERVAL = 30  # seconds


def mark_ai_down():
    """Mark the AI provider as unavailable and log the event."""
    global AI_AVAILABLE, LAST_FAILURE
    if AI_AVAILABLE:
        logger.warning("AI provider unavailable. Switching to fallback mode.")
    AI_AVAILABLE = False
    LAST_FAILURE = datetime.now(timezone.utc)


def mark_ai_up():
    """Mark the AI provider as recovered and log the event."""
    global AI_AVAILABLE
    if not AI_AVAILABLE:
        logger.info("AI provider recovered. Returning to AI mode.")
    AI_AVAILABLE = True


def record_failure():
    """Record a failed AI request. After MAX_FAILURES, disable AI."""
    global CONSECUTIVE_FAILURES
    CONSECUTIVE_FAILURES += 1
    logger.warning(
        "AI failure recorded. Consecutive failures: %s/%s",
        CONSECUTIVE_FAILURES,
        MAX_FAILURES,
    )
    if CONSECUTIVE_FAILURES >= MAX_FAILURES:
        mark_ai_down()


def record_success():
    """Record a successful AI request and reset failure counters."""
    global CONSECUTIVE_FAILURES
    if CONSECUTIVE_FAILURES > 0:
        logger.info(
            "AI success recorded. Resetting failure counter from %s to 0.",
            CONSECUTIVE_FAILURES,
        )
    CONSECUTIVE_FAILURES = 0
    mark_ai_up()


# ---------------------------------------------------------------------------
# Health test
# ---------------------------------------------------------------------------

def _build_test_llm() -> ChatOpenAI:
    """Lightweight LLM instance for health checks only."""
    return ChatOpenAI(
        openai_api_key=API_KEY,
        openai_api_base=API_BASE or None,
        model_name=MODEL,
        max_tokens=5,
    )


async def test_ai_connection():
    """Send a minimal prompt to verify AI connectivity."""
    if not API_KEY:
        raise RuntimeError("API_KEY not configured")

    llm = _build_test_llm()
    await llm.ainvoke([HumanMessage(content="ping")])


# ---------------------------------------------------------------------------
# Background recovery loop
# ---------------------------------------------------------------------------

async def recovery_loop():
    """Continuously monitor AI health and auto-recover when possible."""
    while True:
        if AI_AVAILABLE:
            await asyncio.sleep(RECOVERY_CHECK_INTERVAL)
            continue

        try:
            await test_ai_connection()
            mark_ai_up()
        except Exception:
            # Still down — keep silent to avoid log spam during outages
            pass

        await asyncio.sleep(RECOVERY_CHECK_INTERVAL)