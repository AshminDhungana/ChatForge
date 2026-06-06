from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    session_id: str
    project_id: str
    widget_key: str | None = None

class ChatResponse(BaseModel):
    reply: str
    mode: str    # "ai" or "fallback"