"""
chat.py — ChatForge LangGraph AI Integration
=============================================
Provides get_chat_response() and stream_chat_response(), the only functions
the rest of the app needs.  Public API is identical to the previous version —
main.py requires zero changes.

Replaces the deprecated RunnableWithMessageHistory (LCEL) pattern with the
LangGraph 1.2.4 recommended approach:
  - StateGraph(MessagesState)  — typed state with built-in add_messages reducer
  - MemorySaver checkpointer   — persists conversation history per thread_id
  - graph.ainvoke()            — non-streaming invocation
  - graph.astream_events()     — token-level streaming (version="v2")

The graph is compiled once at module load (not per-request) so the
checkpointer's in-memory state survives across calls.

Falls back to the rule-based engine when no API_KEY is configured, or when
the OpenAI key is invalid.
"""

from __future__ import annotations

from typing import AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI
from openai import AuthenticationError

from langgraph.graph import StateGraph, MessagesState, START, END

from backend.config import (
    API_KEY, API_BASE, MODEL,
    BUSINESS_NAME, BUSINESS_DESCRIPTION,
    BUSINESS_HOURS, BUSINESS_PHONE,
)
from backend.memory import checkpointer

# ---------------------------------------------------------------------------
# System prompt — built once at module load from .env values.
# Prepended to every conversation as a SystemMessage inside the graph node.
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    f"You are a helpful customer service assistant for {BUSINESS_NAME}. "
    f"About us: {BUSINESS_DESCRIPTION}. "
    f"Business hours: {BUSINESS_HOURS}. "
    f"Be concise, friendly, and only answer questions about this business. "
    f"If you don't know something, direct the customer to call {BUSINESS_PHONE}."
)

# ---------------------------------------------------------------------------
# LLM — instantiated once; streaming is handled at the astream_events level
# so a single model instance covers both streaming and non-streaming paths.
# ---------------------------------------------------------------------------

def _build_llm(streaming: bool = False) -> ChatOpenAI:
    return ChatOpenAI(
        openai_api_key=API_KEY,
        openai_api_base=API_BASE or None,   # empty string → None → api.openai.com
        model_name=MODEL,
        streaming=streaming,
    )


# ---------------------------------------------------------------------------
# Graph definition
# ---------------------------------------------------------------------------
# MessagesState is a TypedDict with a single field:
#   messages: Annotated[list[BaseMessage], add_messages]
#
# The add_messages reducer appends new messages to the existing list, so
# LangGraph automatically accumulates the full conversation history in the
# checkpointer without any manual history management.
#
# Node: call_model
#   Input  — full messages list from state (includes prior turns via checkpointer)
#   Output — {"messages": [AIMessage(...)]}  (appended by add_messages reducer)
#
# Graph topology:  START → call_model → END  (single-node, simple chat loop)
# ---------------------------------------------------------------------------

def _make_graph(streaming: bool = False):
    """
    Build and compile a LangGraph chat graph.

    Two separate compiled graphs are created at module load:
      _graph          — for ainvoke()  (non-streaming)
      _streaming_graph — for astream_events()  (streaming)

    Both share the same checkpointer, so session history is unified.
    """
    llm = _build_llm(streaming=streaming)

    async def call_model(state: MessagesState) -> dict:
        """
        Single graph node — calls the LLM with the system prompt prepended.

        The state["messages"] list already contains the full history for this
        thread_id (restored by the checkpointer before the node runs).
        We prepend the system message here so it is never stored in the
        checkpointer (avoids duplicating it on every turn).
        """
        messages = [SystemMessage(content=_SYSTEM_PROMPT)] + state["messages"]
        response: AIMessage = await llm.ainvoke(messages)
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("call_model", call_model)
    builder.add_edge(START, "call_model")
    builder.add_edge("call_model", END)

    return builder.compile(checkpointer=checkpointer)


# Compile once at import time — thread-safe for concurrent async requests.
_graph = _make_graph(streaming=False)
_streaming_graph = _make_graph(streaming=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _thread_config(session_id: str) -> dict:
    """LangGraph config dict that scopes the checkpointer to a session."""
    return {"configurable": {"thread_id": session_id}}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_chat_response(message: str, session_id: str) -> dict:
    """
    Returns {"reply": str, "mode": "ai" | "fallback"}.

    Delegates to the fallback engine when API_KEY is missing or invalid.
    """
    if not API_KEY:
        from backend.fallback import get_fallback_response
        return {"reply": get_fallback_response(message), "mode": "fallback"}

    try:
        result = await _graph.ainvoke(
            {"messages": [HumanMessage(content=message)]},
            config=_thread_config(session_id),
        )
        # result["messages"][-1] is the AIMessage added by call_model
        return {"reply": result["messages"][-1].content, "mode": "ai"}

    except AuthenticationError:
        from backend.fallback import get_fallback_response
        return {"reply": get_fallback_response(message), "mode": "fallback"}


async def stream_chat_response(
    message: str, session_id: str
) -> AsyncIterator[str]:
    """
    Async generator yielding SSE-formatted chunks: 'data: <token>\\n\\n'.

    Uses graph.astream_events(version="v2") and filters for the
    "on_chat_model_stream" event, which fires once per token from the LLM.

    If API_KEY is not set or is invalid, emits the full fallback reply as a
    single chunk, then the terminal 'data: [DONE]\\n\\n' sentinel.
    """
    if not API_KEY:
        from backend.fallback import get_fallback_response
        reply = get_fallback_response(message)
        yield f"data: {reply}\n\n"
        yield "data: [DONE]\n\n"
        return

    try:
        async for event in _streaming_graph.astream_events(
            {"messages": [HumanMessage(content=message)]},
            config=_thread_config(session_id),
            version="v2",                       # recommended; v1 is deprecated
        ):
            if event["event"] == "on_chat_model_stream":
                token: str = event["data"]["chunk"].content
                if token:
                    yield f"data: {token}\n\n"

    except AuthenticationError:
        from backend.fallback import get_fallback_response
        reply = get_fallback_response(message)
        yield f"data: {reply}\n\n"

    yield "data: [DONE]\n\n"