from threading import Lock
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory

# --- In-memory store with a lock for thread safety ---
_sessions: dict[str, ChatMessageHistory] = {}
_lock = Lock()

MAX_SESSIONS = 1000  # guard against unbounded growth


def get_session_history(session_id: str) -> BaseChatMessageHistory:
    """Get or create a ChatMessageHistory for the given session_id."""
    with _lock:
        if session_id not in _sessions:
            if len(_sessions) >= MAX_SESSIONS:
                # Evict the oldest session
                oldest = next(iter(_sessions))
                del _sessions[oldest]
            _sessions[session_id] = ChatMessageHistory()
        return _sessions[session_id]


def delete_session(session_id: str) -> None:
    """Explicitly remove a session (e.g. on logout or conversation end)."""
    with _lock:
        _sessions.pop(session_id, None)