import asyncio
import logging
import uvicorn
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from backend.chat import get_chat_response, stream_chat_response
from backend.models import ChatRequest, ChatResponse
from backend.config import ALLOWED_DOMAINS, PROJECT_ID, WIDGET_API_KEY, RATE_LIMIT
from backend.ai_health import recovery_loop, get_status_dict

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)

app = FastAPI(title="ChatForge")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

cors_origins = set()
for d in ALLOWED_DOMAINS:
    cors_origins.add(f"https://{d}")
    cors_origins.add(f"http://{d}")
    if d in ("localhost", "127.0.0.1"):
        cors_origins.add(f"http://{d}:8000")
        cors_origins.add(f"https://{d}:8000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(cors_origins),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
)


@app.on_event("startup")
async def startup():
    """Start the background AI recovery monitor on server boot."""
    asyncio.create_task(recovery_loop())


@app.get("/health")
def health():
    return {"status": "ok"}


_FAVICON_PATH = Path(__file__).resolve().parent / "static" / "favicon.ico"


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    if _FAVICON_PATH.exists():
        return FileResponse(_FAVICON_PATH)
    return Response(
        content=(
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff"
            b"\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02"
            b"\x44\x01\x00\x3b"
        ),
        media_type="image/gif",
    )


@app.post("/api/v1/chat", response_model=ChatResponse)
@limiter.limit(RATE_LIMIT)
async def chat(chat_request: ChatRequest, request: Request):
    await validate_request(chat_request, request)
    result = await get_chat_response(chat_request.message, chat_request.session_id)
    return ChatResponse(**result)


@app.post("/api/v1/chat/stream")
@limiter.limit(RATE_LIMIT)
async def chat_stream(chat_request: ChatRequest, request: Request):
    """
    Streams the reply token-by-token as Server-Sent Events.
    Content-Type: text/event-stream
    Each chunk: 'data: <token>\\n\\n'
    Final chunk: 'data: [DONE]\\n\\n'
    """
    await validate_request(chat_request, request)
    return StreamingResponse(
        stream_chat_response(chat_request.message, chat_request.session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/v1/config")
def get_widget_config():
    """
    Returns the runtime configuration that widget.js needs to style itself.
    Called once on widget load — no auth required.
    """
    from backend.config import (
        WIDGET_COLOR,
        GREETING_MESSAGE,
        QUICK_REPLIES,
        BUSINESS_NAME,
    )
    return {
        "color":         WIDGET_COLOR,
        "greeting":      GREETING_MESSAGE,
        "quick_replies": QUICK_REPLIES,
        "business_name": BUSINESS_NAME,
    }


@app.get("/api/v1/ai-status")
def ai_status():
    """
    Expose current circuit-breaker health for monitoring and debugging.

    Returns:
        state:           "closed" | "half_open" | "open"
        available:       bool — True only when state is "closed"
        mode:            "ai" | "fallback"
        failures:        consecutive failure count
        last_opened_at:  ISO-8601 timestamp of last circuit opening, or null
    """
    return get_status_dict()


async def validate_request(chat_request: ChatRequest, request: Request):
    if chat_request.project_id != PROJECT_ID:
        raise HTTPException(status_code=401, detail="Invalid project")

    if WIDGET_API_KEY and chat_request.widget_key != WIDGET_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid widget key")

    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")
    domain_ok = any(d in origin or d in referer for d in ALLOWED_DOMAINS)
    if ALLOWED_DOMAINS and not domain_ok:
        raise HTTPException(status_code=403, detail="Domain not allowed")


# Mounted last so it doesn't shadow API routes
app.mount("/", StaticFiles(directory="widget", html=True), name="widget")


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="localhost", port=8000, reload=True)