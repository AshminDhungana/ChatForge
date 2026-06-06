from pydantic import BaseModel, Field
from pydantic import field_validator

class ChatRequest(BaseModel):
    message: str = Field(..., max_length=2000, description="User message, max 2000 characters")
    session_id: str
    project_id: str
    widget_key: str | None = None

    @field_validator("message")
    def validate_message(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Message cannot be empty or whitespace only")
        if len(stripped) > 2000:
            raise ValueError("Message too long (max 2000 characters)")
        return stripped

class ChatResponse(BaseModel):
    reply: str
    mode: str    # "ai" or "fallback"