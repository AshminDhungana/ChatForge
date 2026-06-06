import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from backend.chat import get_chat_response
from backend.models import ChatRequest, ChatResponse
from backend.config import ALLOWED_DOMAINS, PROJECT_ID, WIDGET_API_KEY

from fastapi.responses import FileResponse, StreamingResponse   
from backend.chat import get_chat_response, stream_chat_response  

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from backend.config import RATE_LIMIT


app = FastAPI(title="ChatForge")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"https://{d}" for d in ALLOWED_DOMAINS],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


async def validate_request(chat_request: ChatRequest, http_request: Request):
    if chat_request.project_id != PROJECT_ID:
        raise HTTPException(status_code=401, detail="Invalid project")

    if WIDGET_API_KEY and chat_request.widget_key != WIDGET_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid widget key")

    origin = http_request.headers.get("origin", "")
    referer = http_request.headers.get("referer", "")
    domain_ok = any(d in origin or d in referer for d in ALLOWED_DOMAINS)
    if ALLOWED_DOMAINS and not domain_ok:
        raise HTTPException(status_code=403, detail="Domain not allowed")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.ico")


@app.post("/api/v1/chat", response_model=ChatResponse)
@limiter.limit(RATE_LIMIT)
async def chat(request: ChatRequest, http_request: Request):
    await validate_request(request, http_request)
    result = await get_chat_response(request.message, request.session_id)
    return ChatResponse(**result)

@app.post("/api/v1/chat/stream")
@limiter.limit(RATE_LIMIT)
async def chat_stream(request: ChatRequest, http_request: Request):
    """
    Streams the reply token-by-token as Server-Sent Events.
    Content-Type: text/event-stream
    Each chunk: 'data: <token>\n\n'
    Final chunk: 'data: [DONE]\n\n'
    """
    await validate_request(request, http_request)
    return StreamingResponse(
        stream_chat_response(request.message, request.session_id),
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
 
    Called once on widget load — no auth required (values are non-sensitive
    presentation config, not secrets). Cached by the browser via standard
    HTTP caching on the CDN / reverse proxy in production.
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

# Mounted last so it doesn't shadow API routes
app.mount("/", StaticFiles(directory="widget", html=True), name="widget")


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="localhost", port=8000, reload=True)