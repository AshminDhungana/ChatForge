"""
chat.py — ChatForge LangChain AI Integration
=============================================
Provides get_chat_response(), the single function the rest of the app needs.

Uses the modern LCEL (LangChain Expression Language) API:
  - RunnableWithMessageHistory  (replaces the deprecated ConversationChain)
  - .ainvoke()                  (replaces the removed .arun())
  - ChatPromptTemplate + MessagesPlaceholder for structured prompts

Falls back to the rule-based engine when no API_KEY is configured.
"""

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory

from backend.config import (
    API_KEY, API_BASE, MODEL,
    BUSINESS_NAME, BUSINESS_DESCRIPTION,
    BUSINESS_HOURS, BUSINESS_PHONE,
)
from backend.memory import get_session_history

# ---------------------------------------------------------------------------
# System prompt — injected as the first message in every conversation.
# Built once at module load; all config values come from .env.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    f"You are a helpful customer service assistant for {BUSINESS_NAME}. "
    f"About us: {BUSINESS_DESCRIPTION}. "
    f"Business hours: {BUSINESS_HOURS}. "
    f"Be concise, friendly, and only answer questions about this business. "
    f"If you don't know something, direct the customer to call {BUSINESS_PHONE}."
)


# ---------------------------------------------------------------------------
# Chain builder
# ---------------------------------------------------------------------------

def _build_chain() -> RunnableWithMessageHistory:
    """
    Construct a RunnableWithMessageHistory chain.

    Called per request (not at import time) so:
    - The server starts cleanly even with no API_KEY.
    - A server restart picks up .env changes immediately.
    """
    llm = ChatOpenAI(
        openai_api_key=API_KEY,
        openai_api_base=API_BASE or None,  # empty string → None → defaults to api.openai.com
        model_name=MODEL,
        streaming=False,                   # Phase 8 adds a separate streaming path
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history"),  # injected from memory
        ("human", "{message}"),
    ])

    return RunnableWithMessageHistory(
        prompt | llm,
        get_session_history,            # memory.py — returns ChatMessageHistory per session
        input_messages_key="message",   # must match "{message}" in the prompt
        history_messages_key="chat_history",  # must match the MessagesPlaceholder name
    )


# ---------------------------------------------------------------------------
# Public API — the only function the rest of the app calls
# ---------------------------------------------------------------------------

async def get_chat_response(message: str, session_id: str) -> dict:
    """
    Returns {"reply": str, "mode": "ai" | "fallback"}.

    If API_KEY is not configured, silently delegates to the fallback engine.
    """
    if not API_KEY:
        from backend.fallback import get_fallback_response
        return {"reply": get_fallback_response(message), "mode": "fallback"}

    chain = _build_chain()
    result = await chain.ainvoke(
        {"message": message},
        config={"configurable": {"session_id": session_id}},
    )
    return {"reply": result.content, "mode": "ai"}