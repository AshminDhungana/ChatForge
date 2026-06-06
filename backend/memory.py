from langgraph.checkpoint.memory import MemorySaver

# ---------------------------------------------------------------------------
# Single shared checkpointer — created once at import time.
# MemorySaver (aliased to InMemorySaver in LangGraph 1.2.4) is safe for
# concurrent async access without an explicit lock.
# ---------------------------------------------------------------------------

checkpointer = MemorySaver()


def delete_session(session_id: str) -> None:
    """
    Remove all checkpoint data for a session.

    MemorySaver (LangGraph 1.2.4) stores state in a flat dict keyed by
    thread_id. Deleting the entry clears the full conversation history for
    that session.

    Called on logout or explicit conversation reset — not required for normal
    operation, but prevents unbounded memory growth in long-running servers.
    """
    checkpointer.storage.pop(session_id, None)