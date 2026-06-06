"""
memory.py — ChatForge Session Memory (LangGraph)
=================================================
Provides a single shared MemorySaver checkpointer that LangGraph uses to
persist conversation state across turns.

LangGraph 1.2.4 replaces the old manual ChatMessageHistory + dict approach:
  - MemorySaver  stores the full graph state (including message history)
               keyed by thread_id, which maps 1-to-1 with session_id.
  - No manual locking, no eviction loop — LangGraph manages it internally.
  - The same checkpointer instance is shared across all requests; it is
    thread-safe for concurrent async use.

Public surface
--------------
  checkpointer   — pass to graph.compile(checkpointer=checkpointer)
  delete_session — drop a session (e.g. on logout / conversation end)
"""

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