from __future__ import annotations

from typing import AsyncIterator
from copy import deepcopy

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
from backend.ai_health import (
    AI_AVAILABLE,
    record_failure,
    record_success,
)

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

    Graphs are created lazily on first use (via _get_graph) rather than at
    module load, so a missing API_KEY does not crash the server on startup —
    the fallback path in get_chat_response / stream_chat_response handles it
    before _get_graph is ever called.

    Both graphs share the same checkpointer, so session history is unified.
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


# ---------------------------------------------------------------------------
# Lazy graph cache — graphs are built on first use, not at import time.
# This allows the server to start successfully even when API_KEY is empty,
# because the fallback guards in get_chat_response / stream_chat_response
# run before _get_graph() is ever called.
# ---------------------------------------------------------------------------

_graph = None
_streaming_graph = None


def _get_graph(streaming: bool = False):
    """Return the compiled graph for the requested mode, building it on first call."""
    global _graph, _streaming_graph
    if streaming:
        if _streaming_graph is None:
            _streaming_graph = _make_graph(streaming=True)
        return _streaming_graph
    else:
        if _graph is None:
            _graph = _make_graph(streaming=False)
        return _graph


# Helpers

def _thread_config(session_id: str) -> dict:
    """LangGraph config dict that scopes the checkpointer to a session."""
    return {"configurable": {"thread_id": session_id}}


def _persist_fallback_turn(session_id: str, user_msg: str, reply: str) -> None:
    """
    Manually append a HumanMessage + AIMessage pair to the checkpointer
    storage for the given session_id.

    Called during failover when API_KEY is configured so that when AI
    recovers, the graph loads the full conversation history (including
    fallback turns). Skipped when API_KEY is missing since there is no
    AI to recover to.
    """
    if not session_id:
        return

    checkpoints = checkpointer.storage.get(session_id)
    if checkpoints is None:
        checkpoints = []
        checkpointer.storage[session_id] = checkpoints

    new_messages = [HumanMessage(content=user_msg), AIMessage(content=reply)]

    if checkpoints:
        latest = checkpoints[-1]
        updated = deepcopy(latest)
        if "channel_values" in updated and "messages" in updated["channel_values"]:
            updated["channel_values"]["messages"] = (
                list(updated["channel_values"]["messages"]) + new_messages
            )
        else:
            updated["channel_values"] = {"messages": new_messages}
        checkpoints.append(updated)
    else:
        checkpoints.append({
            "channel_values": {"messages": new_messages},
            "versions_seen": {},
        })


# Public API

async def get_chat_response(message: str, session_id: str) -> dict:
    """
    Returns {"reply": str, "mode": "ai" | "fallback"}.

    Delegates to the fallback engine when API_KEY is missing, AI is marked
    unavailable, or any AI call fails.

    When API_KEY is set and failover occurs, the user message and fallback
    response are persisted into the checkpointer so conversation history
    remains intact upon recovery.
    """
    from backend.fallback import get_fallback_response

    if not API_KEY:
        return {"reply": get_fallback_response(message), "mode": "fallback"}

    if not AI_AVAILABLE:
        reply = get_fallback_response(message)
        _persist_fallback_turn(session_id, message, reply)
        return {"reply": reply, "mode": "fallback"}

    try:
        result = await _get_graph(streaming=False).ainvoke(
            {"messages": [HumanMessage(content=message)]},
            config=_thread_config(session_id),
        )
        record_success()
        return {"reply": result["messages"][-1].content, "mode": "ai"}

    except Exception:
        record_failure()
        reply = get_fallback_response(message)
        _persist_fallback_turn(session_id, message, reply)
        return {"reply": reply, "mode": "fallback"}


async def stream_chat_response(
    message: str, session_id: str
) -> AsyncIterator[str]:
    """
    Async generator yielding SSE-formatted chunks: 'data: <token>\n\n'.

    Uses graph.astream_events(version="v2") and filters for the
    "on_chat_model_stream" event, which fires once per token from the LLM.

    If API_KEY is not set, AI is unavailable, or any error occurs, emits the
    full fallback reply as a single chunk, then the terminal 'data: [DONE]\n\n' sentinel.

    When API_KEY is set and failover occurs, the turn is persisted so
    conversation history remains intact upon recovery.
    """
    from backend.fallback import get_fallback_response

    if not API_KEY:
        reply = get_fallback_response(message)
        yield f"data: {reply}\n\n"
        yield "data: [DONE]\n\n"
        return

    if not AI_AVAILABLE:
        reply = get_fallback_response(message)
        _persist_fallback_turn(session_id, message, reply)
        yield f"data: {reply}\n\n"
        yield "data: [DONE]\n\n"
        return

    try:
        async for event in _get_graph(streaming=True).astream_events(
            {"messages": [HumanMessage(content=message)]},
            config=_thread_config(session_id),
            version="v2",
        ):
            if event["event"] == "on_chat_model_stream":
                token: str = event["data"]["chunk"].content
                if token:
                    yield f"data: {token}\n\n"

        record_success()

    except Exception:
        record_failure()
        reply = get_fallback_response(message)
        _persist_fallback_turn(session_id, message, reply)
        yield f"data: {reply}\n\n"

    yield "data: [DONE]\n\n"