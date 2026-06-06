import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from backend.fallback import get_fallback_response
from backend.models import ChatRequest, ChatResponse
from backend.config import ALLOWED_DOMAINS, PROJECT_ID, WIDGET_API_KEY

app = FastAPI(title="ChatForge")

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
async def chat(request: ChatRequest, http_request: Request):
    await validate_request(request, http_request)
    reply = get_fallback_response(request.message)
    return ChatResponse(reply=reply, mode="fallback")


# Mounted last so it doesn't shadow API routes
app.mount("/", StaticFiles(directory="widget", html=True), name="widget")


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="localhost", port=8000, reload=True)