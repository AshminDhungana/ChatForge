import asyncio
import json
import logging
import uvicorn
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.chat import get_chat_response, stream_chat_response
from backend.models import ChatRequest, ChatResponse
from backend.config import ALLOWED_DOMAINS, PROJECT_ID, WIDGET_API_KEY, RATE_LIMIT
from backend.ai_health import recovery_loop, get_status_dict
from urllib.parse import urlparse

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Custom key function that reads session_id from request.state
# ----------------------------------------------------------------------
def get_session_id(request: Request) -> str:
    """Return session_id previously set by middleware, fallback to IP."""
    session_id = getattr(request.state, "session_id", "")
    if not session_id:
        # Fallback to IP if something went wrong (should not happen)
        from slowapi.util import get_remote_address
        return get_remote_address(request)
    return session_id

# ----------------------------------------------------------------------
# Middleware to extract session_id from POST body
# ----------------------------------------------------------------------
class SessionIdMiddleware(BaseHTTPMiddleware):
    """Extract session_id from JSON body and attach to request.state."""

    async def dispatch(self, request: Request, call_next):
        # Only process POST requests to chat endpoints
        if request.method == "POST" and request.url.path in ("/api/v1/chat", "/api/v1/chat/stream"):
            try:
                body = await request.body()
                if body:
                    data = json.loads(body)
                    session_id = data.get("session_id", "")
                    request.state.session_id = session_id
                    # Re-attach body so FastAPI can parse it later
                    request._body = body
                else:
                    request.state.session_id = ""
            except Exception:
                request.state.session_id = ""
        else:
            request.state.session_id = ""

        response = await call_next(request)
        return response

# ----------------------------------------------------------------------
# FastAPI app setup
# ----------------------------------------------------------------------
app = FastAPI(title="ChatForge")

# Configure rate limiter with custom key function
limiter = Limiter(key_func=get_session_id)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS origins 
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

# session middleware (must be added after CORS but before routes)
app.add_middleware(SessionIdMiddleware)

# ----------------------------------------------------------------------
# Startup & health
# ----------------------------------------------------------------------
@app.on_event("startup")
async def startup():
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

# ----------------------------------------------------------------------
# API endpoints
# ----------------------------------------------------------------------
@app.post("/api/v1/chat", response_model=ChatResponse)
@limiter.limit(RATE_LIMIT)
async def chat(chat_request: ChatRequest, request: Request):
    await validate_request(chat_request, request)
    result = await get_chat_response(chat_request.message, chat_request.session_id)
    return ChatResponse(**result)

@app.post("/api/v1/chat/stream")
@limiter.limit(RATE_LIMIT)
async def chat_stream(chat_request: ChatRequest, request: Request):
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
    return get_status_dict()

# ----------------------------------------------------------------------
# Validation helper 
# ----------------------------------------------------------------------
def is_allowed_origin(origin: str, allowed_domains: list) -> bool:
    """Check if the origin's hostname matches an allowed domain."""
    if not origin or not allowed_domains:
        return False
    try:
        parsed = urlparse(origin)
        hostname = parsed.hostname
        if not hostname:
            return False
        # Normalize: remove port if present (origin may include port)
        hostname = hostname.split(':')[0]
        for domain in allowed_domains:
            if hostname == domain or hostname.endswith('.' + domain):
                return True
    except Exception:
        return False
    return False

def is_allowed_referer(referer: str, allowed_domains: list) -> bool:
    """Check if the referer URL's hostname matches an allowed domain."""
    if not referer or not allowed_domains:
        return False
    try:
        parsed = urlparse(referer)
        hostname = parsed.hostname
        if not hostname:
            return False
        hostname = hostname.split(':')[0]
        for domain in allowed_domains:
            if hostname == domain or hostname.endswith('.' + domain):
                return True
    except Exception:
        return False
    return False

async def validate_request(chat_request: ChatRequest, request: Request):
    if chat_request.project_id != PROJECT_ID:
        raise HTTPException(status_code=401, detail="Invalid project")

    if WIDGET_API_KEY and chat_request.widget_key != WIDGET_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid widget key")

    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")
    
    # At least one header must match the allowed domains
    domain_ok = (is_allowed_origin(origin, ALLOWED_DOMAINS) or 
                 is_allowed_referer(referer, ALLOWED_DOMAINS))
    
    if ALLOWED_DOMAINS and not domain_ok:
        raise HTTPException(status_code=403, detail="Domain not allowed")

# ----------------------------------------------------------------------
# Static widget 
# ----------------------------------------------------------------------
app.mount("/", StaticFiles(directory="widget", html=True), name="widget")

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="localhost", port=8000, reload=True)