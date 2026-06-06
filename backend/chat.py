from __future__ import annotations

from typing import AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI

from langgraph.graph import StateGraph, MessagesState, START, END

from backend.config import (
    API_KEY, API_BASE, MODEL,
    BUSINESS_NAME, BUSINESS_DESCRIPTION,
    BUSINESS_HOURS, BUSINESS_PHONE,
)
from backend.memory import checkpointer
from backend.ai_health import (
    CircuitState,
    get_circuit_state,
    record_failure,
    record_success,
)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    f"You are a helpful customer service assistant for {BUSINESS_NAME}. "
    f"About us: {BUSINESS_DESCRIPTION}. "
    f"Business hours: {BUSINESS_HOURS}. "
    f"Be concise, friendly, and only answer questions about this business. "
    f"If you don't know something, direct the customer to call {BUSINESS_PHONE}."
)

# ---------------------------------------------------------------------------
# Single LLM instance — streaming is requested at call-site, not here.
# Using streaming=False on the model is fine; astream_events() handles
# token-by-token delivery regardless of this flag when version="v2".
# ---------------------------------------------------------------------------

def _build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        openai_api_key=API_KEY,
        openai_api_base=API_BASE or None,
        model_name=MODEL,
    )


# ---------------------------------------------------------------------------
# Single compiled graph (lazy, built on first request)
# ---------------------------------------------------------------------------

_graph = None


def _get_graph():
    """Return the compiled graph, building it on first call."""
    global _graph
    if _graph is None:
        llm = _build_llm()

        async def call_model(state: MessagesState) -> dict:
            messages = [SystemMessage(content=_SYSTEM_PROMPT)] + state["messages"]
            response: AIMessage = await llm.ainvoke(messages)
            return {"messages": [response]}

        builder = StateGraph(MessagesState)
        builder.add_node("call_model", call_model)
        builder.add_edge(START, "call_model")
        builder.add_edge("call_model", END)
        _graph = builder.compile(checkpointer=checkpointer)

    return _graph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _thread_config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_chat_response(message: str, session_id: str) -> dict:
    """
    Returns {"reply": str, "mode": "ai" | "fallback"}.

    Routes to fallback when:
    - API_KEY is missing
    - Circuit is OPEN (provider known-down)
    - Circuit is HALF_OPEN (recovery probe in progress — protect real users
      from an unstable provider; the probe itself runs via recovery_loop)
    - An exception occurs during the AI call
    """
    from backend.fallback import get_fallback_response

    if not API_KEY:
        return {"reply": get_fallback_response(message), "mode": "fallback"}

    state = await get_circuit_state()
    if state in (CircuitState.OPEN, CircuitState.HALF_OPEN):
        return {"reply": get_fallback_response(message), "mode": "fallback"}

    try:
        result = await _get_graph().ainvoke(
            {"messages": [HumanMessage(content=message)]},
            config=_thread_config(session_id),
        )
        await record_success()
        return {"reply": result["messages"][-1].content, "mode": "ai"}

    except Exception as exc:
        await record_failure(exc)
        return {"reply": get_fallback_response(message), "mode": "fallback"}


async def stream_chat_response(
    message: str, session_id: str
) -> AsyncIterator[str]:
    """
    Async generator yielding SSE-formatted chunks: 'data: <token>\\n\\n'.

    Terminal sentinel: 'data: [DONE]\\n\\n'.

    Falls back to a single-chunk fallback reply when:
    - API_KEY is missing
    - Circuit is OPEN or HALF_OPEN
    - Any exception occurs during streaming
    """
    from backend.fallback import get_fallback_response

    if not API_KEY:
        yield f"data: {get_fallback_response(message)}\n\n"
        yield "data: [DONE]\n\n"
        return

    state = await get_circuit_state()
    if state in (CircuitState.OPEN, CircuitState.HALF_OPEN):
        yield f"data: {get_fallback_response(message)}\n\n"
        yield "data: [DONE]\n\n"
        return

    try:
        async for event in _get_graph().astream_events(
            {"messages": [HumanMessage(content=message)]},
            config=_thread_config(session_id),
            version="v2",
        ):
            if event["event"] == "on_chat_model_stream":
                token: str = event["data"]["chunk"].content
                if token:
                    yield f"data: {token}\n\n"

        await record_success()

    except Exception as exc:
        await record_failure(exc)
        yield f"data: {get_fallback_response(message)}\n\n"

    yield "data: [DONE]\n\n"