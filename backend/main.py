import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from backend.fallback import get_fallback_response
from backend.models import ChatRequest, ChatResponse


app = FastAPI(title="ChatForge")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    reply = get_fallback_response(request.message)
    return ChatResponse(reply=reply, mode="fallback")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.ico")


# Place after API routes
app.mount("/", StaticFiles(directory="widget", html=True), name="widget")


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="localhost", port=8000, reload=True)