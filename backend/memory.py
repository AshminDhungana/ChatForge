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

    For LangGraph >= 1.2.4, MemorySaver provides the delete_thread() method.
    If that method is unavailable (older version), we manually iterate over
    the internal storage and delete all keys where the first element (thread_id)
    matches the given session_id.
    """
    # Preferred API (LangGraph 1.2.4+)
    if hasattr(checkpointer, "delete_thread"):
        checkpointer.delete_thread(session_id)
        return

    # Fallback for older versions (or if delete_thread is missing)
    # Storage keys are tuples: (thread_id, checkpoint_id)
    keys_to_delete = [
        key for key in checkpointer.storage.keys()
        if isinstance(key, tuple) and len(key) >= 1 and key[0] == session_id
    ]
    for key in keys_to_delete:
        checkpointer.storage.pop(key, None)