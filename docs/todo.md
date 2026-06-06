# ChatForge — Developer Build Guide

This guide walks you through building ChatForge from scratch, phase by phase.
Each phase builds on the previous one. **Do not skip phases** — later phases
depend on what you build earlier. Read every section before writing code for it.

> **You will know a phase is complete when the checkpoint at the end of it passes.**

---

## Prerequisites

Before you write a single line of code, make sure you have these installed:

- [x] **Python 3.10 or higher** — run `python --version` to check
- [x] **pip** — run `pip --version` to check
- [x] **Git** — run `git --version` to check
- [x] A code editor (VS Code is recommended if you don't have one)
- [x] A terminal / command prompt you're comfortable using

> **New to any of these?** Install Python from https://python.org, Git from
> https://git-scm.com. VS Code from https://code.visualstudio.com.

---

## Phase 0 — Project Setup

**Goal:** Get the repository on your machine with the right folder structure and
dependencies installed.

### 0.1 Clone the repository

```bash
git clone https://github.com/AshminDhungana/chatforge.git
cd chatforge
```

### 0.2 Understand the folder structure

Before touching anything, open the project in your editor and look at every
file and folder. Cross-reference with `docs/architecture.md`. You should be
able to answer:

- What does each file in `backend/` do?
- What is `widget/` for?
- What is `.env.example` for?

### 0.3 Create your virtual environment

A virtual environment keeps your project's dependencies isolated from the rest
of your computer. Always use one.

```bash
python -m venv venv
```

Activate it:

- **Mac / Linux:** `source venv/bin/activate`
- **Windows:** `venv\Scripts\activate`

You should see `(venv)` appear in your terminal prompt. This means it's active.

> **Important:** Every time you open a new terminal to work on this project,
> activate the virtual environment again before running any commands.

### 0.4 Install dependencies

```bash
pip install -r requirements.txt
```

If this fails, make sure your virtual environment is active and that you are
inside the `chatforge/` directory.

### 0.5 Set up your environment file

```bash
cp .env.example .env
```

Open `.env` and replace the placeholder values with something real — use the
example business (Mario's Pizza) for now. You will fill in the AI keys later.

### ✅ Phase 0 Checkpoint

- [x] Running `python --version` inside `venv` shows 3.10+
- [x] Running `pip list` shows fastapi, uvicorn, langchain-openai, and **langgraph==1.2.4**
- [x] A `.env` file exists in the project root
- [x] You can describe what each file in `backend/` is for

---

## Phase 1 — Configuration Loader

**Goal:** Build `backend/config.py` so all other backend files can read `.env`
values in one place. This is the foundation everything else depends on.

**Why start here?** Every other module (`main.py`, `chat.py`, `fallback.py`)
will need access to env values like `BUSINESS_NAME`, `API_KEY`, and
`RATE_LIMIT`. If you hardcode those values in each file, changing one setting
means editing five files. A central config loader means you change it once.

### 1.1 What this file needs to do

`backend/config.py` should:

- Load the `.env` file using `python-dotenv`
- Expose every environment variable as a Python variable or object attribute
- Provide sensible defaults for optional variables (e.g. `RATE_LIMIT` defaults
  to `"20/minute"` if not set)

### 1.2 Variables to expose

Cover all variables from `.env.example`:

```
BUSINESS_NAME, BUSINESS_DESCRIPTION, BUSINESS_HOURS,
BUSINESS_PHONE, BUSINESS_ADDRESS, BUSINESS_WEBSITE,
PROJECT_ID, ALLOWED_DOMAINS, WIDGET_API_KEY,
QUICK_REPLIES, API_KEY, API_BASE, MODEL,
WIDGET_COLOR, GREETING_MESSAGE, RATE_LIMIT
```

### 1.3 How to load env variables in Python

```python
from dotenv import load_dotenv
import os

load_dotenv()

BUSINESS_NAME = os.getenv("BUSINESS_NAME", "My Business")
```

`os.getenv("KEY", "default")` returns the value from `.env`, or the default
if the key is missing. Use `None` as the default for truly optional variables
like `API_KEY`.

### 1.4 Handling list-type variables

`QUICK_REPLIES` and `ALLOWED_DOMAINS` are stored as comma-separated strings
in `.env`. Parse them into Python lists:

```python
raw = os.getenv("QUICK_REPLIES", "")
QUICK_REPLIES = [r.strip() for r in raw.split(",") if r.strip()]
```

Do the same for `ALLOWED_DOMAINS`.

### ✅ Phase 1 Checkpoint

Open a Python shell in your terminal (`python`) and run:

```python
from backend.config import BUSINESS_NAME, API_KEY, QUICK_REPLIES, ALLOWED_DOMAINS
print(BUSINESS_NAME)      # Should print Mario's Pizza (or your value)
print(type(QUICK_REPLIES)) # Should print <class 'list'>
print(type(ALLOWED_DOMAINS)) # Should print <class 'list'>
```

- [x] All values load without errors
- [x] `QUICK_REPLIES` and `ALLOWED_DOMAINS` are Python lists, not strings
- [x] Missing optional keys don't crash the import

---

## Phase 2 — Bare FastAPI Server

**Goal:** Build a minimal `backend/main.py` that starts a server and responds
to a basic health-check request. No AI, no chat — just a working server.

**Why?** Getting the server running first means you can test every feature you
add in a real browser/terminal instead of guessing whether it works.

### 2.1 Create the FastAPI app

```python
from fastapi import FastAPI

app = FastAPI(title="ChatForge")

@app.get("/health")
def health():
    return {"status": "ok"}
```

### 2.2 Serve `widget.js` as a static file

The embed snippet in the README loads `widget.js` directly from the server.
FastAPI can serve static files using `StaticFiles`:

```python
from fastapi.staticfiles import StaticFiles

app.mount("/", StaticFiles(directory="widget", html=True), name="widget")
```

> **Note:** The static files mount should come after your API routes, or it
> will intercept them.

### 2.3 Add CORS middleware

The widget runs on a different domain than the server. Without CORS headers,
browsers will block widget requests. Add this early in `main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You will tighten this in Phase 5
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2.4 Start the server

```bash
uvicorn backend.main:app --reload
```

`--reload` means the server restarts automatically when you save a file.
Leave this running in a terminal tab while you develop.

### ✅ Phase 2 Checkpoint

- [x] `http://localhost:8000/health` returns `{"status": "ok"}` in your browser
- [x] `http://localhost:8000/docs` shows the FastAPI interactive docs page
- [x] Saving a change to `main.py` causes the server to reload in the terminal
- [x] No import errors on startup

---

## Phase 3 — Fallback Engine

**Goal:** Build `backend/fallback.py` — the rule-based response engine that
works with zero AI configuration.

**Why build this before the AI chat?** The fallback is simpler (no external
API calls, no async code) and it lets you test the full request/response cycle
before adding the complexity of the LLM. You will use it to verify your chat
endpoint works before wiring up the model.

### 3.1 What the fallback engine does

It receives a message string and returns a plain text response string. It uses
keyword matching — no machine learning, no API calls.

Flow:

```
message comes in → check for keywords → return matching FAQ answer → no match → return contact info
```

### 3.2 Keywords to handle

At minimum, detect intent for:

- **Hours** — keywords like `hours`, `open`, `close`, `when`
- **Location / address** — keywords like `where`, `address`, `location`, `find`
- **Contact** — keywords like `phone`, `call`, `contact`, `email`
- **Website** — keywords like `website`, `online`, `url`

Use the config values from Phase 1 to build the responses:

```python
from backend.config import BUSINESS_HOURS, BUSINESS_ADDRESS, BUSINESS_PHONE

def get_fallback_response(message: str) -> str:
    msg = message.lower()
    if any(word in msg for word in ["hours", "open", "close"]):
        return f"We are open {BUSINESS_HOURS}."
    # ... and so on
    return f"Please contact us at {BUSINESS_PHONE} for more information."
```

### 3.3 No match case

If no keyword matches, return the business contact info — phone number, website,
or both. Never return an empty string or an error.

### ✅ Phase 3 Checkpoint

Open a Python shell and test manually:

```python
from backend.fallback import get_fallback_response
print(get_fallback_response("What are your hours?"))
print(get_fallback_response("Where are you located?"))
print(get_fallback_response("asdfghjkl"))  # Should return contact info, not crash
```

- [x] Hours question returns a string containing your business hours
- [x] Location question returns a string containing your address
- [x] Unrecognised input returns a helpful fallback, not an error
- [x] No external API calls are made (this must work fully offline)

---

## Phase 4 — Chat Endpoint (Fallback Mode)

**Goal:** Add a `POST /api/v1/chat` route to `main.py` that accepts a message
and returns a response — using the fallback engine for now.

**Why before AI?** This gets the full request/response cycle working end-to-end
so you can test it with real HTTP calls. Plugging in the LLM in Phase 7 will
then be a contained change to one function, not a structural change.

### 4.1 Define the request and response models

FastAPI uses Pydantic models to validate incoming JSON. Add these to `main.py`
or a separate `models.py`:

```python
from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    session_id: str
    project_id: str
    widget_key: str | None = None

class ChatResponse(BaseModel):
    reply: str
    mode: str  # "ai" or "fallback"
```

### 4.2 Add the chat route

```python
from backend.fallback import get_fallback_response

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    reply = get_fallback_response(request.message)
    return ChatResponse(reply=reply, mode="fallback")
```

### 4.3 Test with curl or the FastAPI docs

Open `http://localhost:8000/docs`, find `POST /api/v1/chat`, click
**Try it out**, and send:

```json
{
  "message": "What are your hours?",
  "session_id": "test-123",
  "project_id": "marios-pizza"
}
```

You can also use curl:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are your hours?", "session_id": "abc", "project_id": "marios-pizza"}'
```

### ✅ Phase 4 Checkpoint

- [x] `POST /api/v1/chat` returns a JSON response with `reply` and `mode` fields
- [x] `mode` is `"fallback"`
- [x] Sending a bad request (e.g. missing `message`) returns a 422 error automatically
- [x] The endpoint appears in `/docs`

---

## Phase 5 — Widget Security & Validation

**Goal:** Add domain validation and widget key checking to the chat endpoint so
only authorised requests get responses.

**Why before AI?** Security should be in place before you attach a real API key.
You don't want to accidentally expose a live LLM endpoint to the world while
still testing.

### 5.1 What to validate on every chat request

Check these on every request to `/api/v1/chat`:

1. `project_id` in the request body matches `PROJECT_ID` from config
2. If `WIDGET_API_KEY` is set in config, `widget_key` in the request must match
3. The `Origin` or `Referer` header domain must be in `ALLOWED_DOMAINS`

### 5.2 Return the right HTTP errors

| Condition                  | HTTP status | Message                |
| -------------------------- | ----------- | ---------------------- |
| `project_id` doesn't match | 401         | `"Invalid project"`    |
| `widget_key` doesn't match | 401         | `"Invalid widget key"` |
| Domain not in allowed list | 403         | `"Domain not allowed"` |

Use FastAPI's `HTTPException`:

```python
from fastapi import HTTPException, Request

def validate_request(chat_request: ChatRequest, http_request: Request):
    from backend.config import PROJECT_ID, WIDGET_API_KEY, ALLOWED_DOMAINS

    if chat_request.project_id != PROJECT_ID:
        raise HTTPException(status_code=401, detail="Invalid project")

    if WIDGET_API_KEY and chat_request.widget_key != WIDGET_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid widget key")

    origin = http_request.headers.get("origin", "")
    referer = http_request.headers.get("referer", "")
    domain_ok = any(d in origin or d in referer for d in ALLOWED_DOMAINS)
    if ALLOWED_DOMAINS and not domain_ok:
        raise HTTPException(status_code=403, detail="Domain not allowed")
```

Call `validate_request()` at the top of your chat handler.

### 5.3 Tighten CORS

Now that domain validation is in place, update the CORS middleware to only
allow your configured domains instead of `"*"`:

```python
from backend.config import ALLOWED_DOMAINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"https://{d}" for d in ALLOWED_DOMAINS],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)
```

> **Local development note:** `localhost` won't be in `ALLOWED_DOMAINS`, so
> requests from `http://localhost:8000/docs` will be blocked. For local testing,
> temporarily add `"localhost"` to `ALLOWED_DOMAINS` in your `.env` and remove
> it before deploying.

### ✅ Phase 5 Checkpoint

Test these cases with curl:

- [x] Correct `project_id`, correct `widget_key` → 200 response
- [x] Wrong `project_id` → 401
- [x] Wrong `widget_key` → 401
- [x] No `widget_key` when `WIDGET_API_KEY` is set in `.env` → 401

---

## Phase 6 — Session Memory Manager

**Goal:** Build `backend/memory.py` to provide a LangGraph-native checkpointer
that persists full conversation state per session.

**Why a separate file?** Both the non-streaming and streaming chat paths need
to share the same state store. Centralising the checkpointer ensures a single
source of truth for session history and makes cleanup straightforward.

### 6.1 What this module needs

A single shared `MemorySaver` instance from `langgraph.checkpoint.memory`.
This is LangGraph's built-in in-memory checkpointer that stores the complete
graph state (including the message list) keyed by `thread_id`, which maps
1-to-1 with `session_id`.

```python
from langgraph.checkpoint.memory import MemorySaver

# Single shared checkpointer — created once at import time.
# MemorySaver is safe for concurrent async access without an explicit lock.
checkpointer = MemorySaver()

def delete_session(session_id: str) -> None:
    """
    Remove all checkpoint data for a session.

    MemorySaver stores state in a flat dict keyed by thread_id.
    Deleting the entry clears the full conversation history for that session.
    """
    checkpointer.storage.pop(session_id, None)
```

### 6.2 What `MemorySaver` does

When a `StateGraph` is compiled with `checkpointer=checkpointer` and invoked
with `config={"configurable": {"thread_id": session_id}}`, LangGraph
automatically:

1. Retrieves the existing state for that `thread_id` before the run starts.
2. Appends new messages via the `MessagesState` `add_messages` reducer during
   execution.
3. Writes the updated state back to the checkpointer after the run completes.

The entire conversation history is managed by LangGraph — no manual dictionary,
no locking, and no message list maintenance required.

### 6.3 Memory lifetime

State lives in-process (in `MemorySaver`'s internal storage). It is
automatically cleared when the server restarts. There is no database —
intentional for the v1 design. Call `delete_session()` to explicitly clear a
session and prevent unbounded growth in long-running servers.

### ✅ Phase 6 Checkpoint

```python
from backend.memory import checkpointer
from langgraph.graph import StateGraph, MessagesState, START, END
from langchain_core.messages import HumanMessage

# Verify checkpointer type
print(type(checkpointer))  # <class 'langgraph.checkpoint.memory.MemorySaver'>

# Build a minimal graph to test state persistence
builder = StateGraph(MessagesState)
builder.add_node("test", lambda state: {"messages": [HumanMessage(content="hi")]})
builder.add_edge(START, "test")
builder.add_edge("test", END)
graph = builder.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "session-abc"}}
r1 = graph.invoke({"messages": []}, config=config)
r2 = graph.invoke({"messages": []}, config=config)

print(len(r1["messages"]))  # 1
print(len(r2["messages"]))  # 2  — history was persisted across invocations
```

- [x] `checkpointer` is a `MemorySaver` instance
- [x] Same `thread_id` accumulates state across invocations
- [x] Different `thread_id` values start with fresh state
- [x] `delete_session()` cleanly removes a session

---

## Phase 7 — LangGraph AI Chat

**Goal:** Build `backend/chat.py` with the LangGraph integration using the
modern `StateGraph` API. Update the chat endpoint to use the LLM when an API
key is configured, falling back to Phase 3's engine when it isn't.

### 7.1 Provider compatibility — any OpenAI-format API works

`ChatOpenAI` from `langchain-openai` speaks the OpenAI REST format. Any
provider that exposes an OpenAI-compatible endpoint works as a drop-in by
setting `API_BASE` and `MODEL` in `.env`. **No code changes required between
providers** — only `.env` values change.

The three required config values are:

| Config key | What it controls                            |
| ---------- | ------------------------------------------- |
| `API_KEY`  | The secret key issued by your provider      |
| `API_BASE` | The provider's base URL (must end at `/v1`) |
| `MODEL`    | The model name as the provider labels it    |

`API_BASE` defaults to `None`, which makes `ChatOpenAI` use OpenAI's own
endpoint automatically. Set it to override.

**Example `.env` values for common providers:**

```ini
# Groq (free tier, fast)
API_KEY="gsk_..."
API_BASE="https://api.groq.com/openai/v1"
MODEL="llama3-8b-8192"

# OpenAI
API_KEY="sk-..."
API_BASE=""          # leave blank — ChatOpenAI defaults to OpenAI
MODEL="gpt-4o-mini"

# OpenRouter (routes to many models)
API_KEY="sk-or-..."
API_BASE="https://openrouter.ai/api/v1"
MODEL="mistralai/mistral-7b-instruct"

# Together AI
API_KEY="..."
API_BASE="https://api.together.xyz/v1"
MODEL="meta-llama/Llama-3-8b-chat-hf"

# Ollama (local, no key needed)
API_KEY="ollama"     # any non-empty string to satisfy validation
API_BASE="http://localhost:11434/v1"
MODEL="llama3"
```

### 7.2 What `chat.py` needs to do

- Accept a `message` and `session_id`
- If `API_KEY` is set: send the message through the compiled LangGraph and
  return the LLM reply
- If `API_KEY` is not set: call the fallback engine and return that reply
- Return both the reply text and the mode (`"ai"` or `"fallback"`)

### 7.3 Setting up the LangGraph chat graph

LangGraph replaces legacy LCEL chains and `RunnableWithMessageHistory` with a
state-machine approach. We define a `StateGraph(MessagesState)` where
`MessagesState` is a TypedDict with a `messages` field annotated with
`add_messages`. This reducer automatically appends new messages to existing
history instead of replacing it.

**Graph topology:** `START → call_model → END` (single-node chat loop)

The `call_model` node:

- Receives the full `messages` list from `state` (already restored by the
  checkpointer for this `thread_id`).
- Prepends a `SystemMessage` with business context. This is done **inside the
  node** so the system prompt is never stored in the checkpointer, avoiding
  duplication on every turn.
- Calls the LLM via `await llm.ainvoke(messages)`.
- Returns `{"messages": [AIMessage(...)]}` which the `add_messages` reducer
  appends to state.

Two compiled graphs are created at module load:

- `_graph` — for `ainvoke()` (non-streaming)
- `_streaming_graph` — for `astream_events()` (streaming)

Both share the **same** `MemorySaver` checkpointer from Phase 6, so session
history is unified across both paths.

```python
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI
from openai import AuthenticationError
from langgraph.graph import StateGraph, MessagesState, START, END

from backend.config import (
    API_KEY, API_BASE, MODEL,
    BUSINESS_NAME, BUSINESS_DESCRIPTION,
    BUSINESS_HOURS, BUSINESS_PHONE,
)
from backend.memory import checkpointer

_SYSTEM_PROMPT = (
    f"You are a helpful customer service assistant for {BUSINESS_NAME}. "
    f"About us: {BUSINESS_DESCRIPTION}. "
    f"Business hours: {BUSINESS_HOURS}. "
    f"Be concise, friendly, and only answer questions about this business. "
    f"If you don't know something, direct the customer to call {BUSINESS_PHONE}."
)

def _build_llm(streaming: bool = False) -> ChatOpenAI:
    return ChatOpenAI(
        openai_api_key=API_KEY,
        openai_api_base=API_BASE or None,   # None → OpenAI's default endpoint
        model_name=MODEL,
        streaming=streaming,
    )

def _make_graph(streaming: bool = False):
    llm = _build_llm(streaming=streaming)

    async def call_model(state: MessagesState) -> dict:
        messages = [SystemMessage(content=_SYSTEM_PROMPT)] + state["messages"]
        response: AIMessage = await llm.ainvoke(messages)
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("call_model", call_model)
    builder.add_edge(START, "call_model")
    builder.add_edge("call_model", END)

    return builder.compile(checkpointer=checkpointer)

# Compile once at import time — thread-safe for concurrent async requests.
_graph = _make_graph(streaming=False)
_streaming_graph = _make_graph(streaming=True)

def _thread_config(session_id: str) -> dict:
    """LangGraph config dict that scopes the checkpointer to a session."""
    return {"configurable": {"thread_id": session_id}}

async def get_chat_response(message: str, session_id: str) -> dict:
    if not API_KEY:
        from backend.fallback import get_fallback_response
        return {"reply": get_fallback_response(message), "mode": "fallback"}

    try:
        result = await _graph.ainvoke(
            {"messages": [HumanMessage(content=message)]},
            config=_thread_config(session_id),
        )
        # result["messages"][-1] is the AIMessage added by call_model
        return {"reply": result["messages"][-1].content, "mode": "ai"}

    except AuthenticationError:
        from backend.fallback import get_fallback_response
        return {"reply": get_fallback_response(message), "mode": "fallback"}
```

Key details:

- `openai_api_base=API_BASE or None` — an empty string in `.env` safely
  becomes `None`, which makes `ChatOpenAI` fall back to OpenAI's default URL.
- `openai_api_key` — passed straight from config; never hardcoded.
- The system prompt is prepended inside the graph node, not injected via a
  prompt template, eliminating prompt-template overhead and checkpointer bloat.
- The same `_make_graph()` function works for every provider; switching
  providers is purely a `.env` change.

### 7.4 Update the chat endpoint

Replace the direct fallback call in `main.py` with:

```python
from backend.chat import get_chat_response

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request):
    await validate_request(request, http_request)
    result = await get_chat_response(request.message, request.session_id)
    return ChatResponse(**result)
```

### 7.5 Install updated dependencies

```bash
pip install langgraph==1.2.4 langchain-core langchain-openai
```

> LangGraph 1.2.4 is the orchestration layer. `langchain-core` provides message
> types and the `ChatOpenAI` interface lives in `langchain-openai`. No legacy
> `langchain` or `langchain-community` packages are required for the chat and
> memory stack.

### ✅ Phase 7 Checkpoint

- [x] With `API_KEY` set: chat endpoint returns `"mode": "ai"` and a real LLM reply
- [x] With `API_KEY` removed from `.env`: endpoint returns `"mode": "fallback"` without crashing
- [x] Sending two messages in the same session — the second reply references context from the first
- [x] Two different `session_id` values don't share conversation history
- [x] Swapping provider (e.g. Groq → OpenRouter) requires only `.env` changes — no code edits
- [x] No deprecation warnings in the server logs

---

## Phase 8 — Streaming Endpoint

**Goal:** Add `POST /api/v1/chat/stream` that streams tokens to the client in
real time using Server-Sent Events (SSE).

**Why streaming?** Without it, the user sees nothing until the full reply is
generated — which can take several seconds. Streaming sends each word as it's
produced, making the response feel instant.

### 8.1 How SSE streaming works

The server sends a response with `Content-Type: text/event-stream`. Instead of
one response body, it sends multiple chunks over time, each formatted as:

```
data: <token>\n\n
```

The client reads these chunks one by one and appends each token to the UI.

### 8.2 LangGraph streaming with `astream_events()`

LangGraph provides `astream_events(version="v2")` which emits fine-grained
events during graph execution. For streaming LLM tokens, filter for the
`"on_chat_model_stream"` event, which fires once per token from the model.

The graph state and checkpointer still manage history automatically during
streaming — after the stream completes, the full assistant message is written
to the checkpointer just like in the non-streaming path.

```python
from fastapi.responses import StreamingResponse

async def stream_chat_response(message: str, session_id: str):
    if not API_KEY:
        from backend.fallback import get_fallback_response
        reply = get_fallback_response(message)
        yield f"data: {reply}\n\n"
        yield "data: [DONE]\n\n"
        return

    try:
        async for event in _streaming_graph.astream_events(
            {"messages": [HumanMessage(content=message)]},
            config=_thread_config(session_id),
            version="v2",                       # recommended; v1 is deprecated
        ):
            if event["event"] == "on_chat_model_stream":
                token: str = event["data"]["chunk"].content
                if token:
                    yield f"data: {token}\n\n"

    except AuthenticationError:
        from backend.fallback import get_fallback_response
        reply = get_fallback_response(message)
        yield f"data: {reply}\n\n"

    yield "data: [DONE]\n\n"

@app.post("/api/v1/chat/stream")
async def chat_stream(request: ChatRequest, http_request: Request):
    await validate_request(request, http_request)
    return StreamingResponse(
        stream_chat_response(request.message, request.session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

> **Note:** Streaming only works when `API_KEY` is set. If there's no API key,
> the generator falls back to yielding the full fallback response as a single
> SSE chunk followed by the terminal `data: [DONE]\n\n` sentinel.

### 8.3 Test streaming manually

```bash
curl -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me about your menu", "session_id": "s1", "project_id": "marios-pizza", "widget_key": "change-me-to-a-random-secret"}'
```

You should see tokens appearing one by one in the terminal output.

### ✅ Phase 8 Checkpoint

- [x] Streaming endpoint returns `Content-Type: text/event-stream`
- [x] Tokens appear incrementally in the terminal (not all at once)
- [x] Streaming with no `API_KEY` still returns something — it doesn't hang or crash
- [x] Memory is updated after a streamed conversation (next message has context)

---

## Phase 9 — Rate Limiting

**Goal:** Add per-session rate limiting to both chat endpoints using `slowapi`.

### 9.1 Set up SlowAPI

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from backend.config import RATE_LIMIT

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

### 9.2 Apply the rate limit decorator

```python
@app.post("/api/v1/chat")
@limiter.limit(RATE_LIMIT)
async def chat(request: ChatRequest, http_request: Request):
    ...

@app.post("/api/v1/chat/stream")
@limiter.limit(RATE_LIMIT)
async def chat_stream(request: ChatRequest, http_request: Request):
    ...
```

SlowAPI reads the `RATE_LIMIT` string (`"20/minute"`) directly — no parsing
needed.

### 9.3 Test rate limiting

Temporarily set `RATE_LIMIT="3/minute"` in `.env`, restart the server, and
send 4 requests in quick succession. The 4th should return a 429 error.
Reset to `"20/minute"` after testing.

### ✅ Phase 9 Checkpoint

- [x] Normal usage (under limit) works as before
- [x] Exceeding the rate limit returns HTTP 429
- [x] Changing `RATE_LIMIT` in `.env` and restarting changes the limit

---

## Phase 10 — Frontend Widget

**Goal:** Build `widget/widget.js` and `widget/index.html` — the embeddable
chat UI that businesses drop onto their websites.

### 10.1 What `widget.js` needs to do

When embedded via `<script>`, it should:

1. Read `data-project-id` and `data-widget-key` from the script tag
2. Inject a chat button (bubble) into the bottom-right corner of the page
3. On click, open a chat panel
4. On message submit, call `POST /api/v1/chat/stream` and stream the reply
5. Display quick reply buttons from `QUICK_REPLIES` at the start of the chat
6. Generate a unique UUID for `session_id` on load (one per page visit)

### 10.2 Reading script tag attributes

```javascript
const script = document.currentScript;
const projectId = script.getAttribute("data-project-id");
const widgetKey = script.getAttribute("data-widget-key");
const serverUrl = script.src.replace("/widget.js", "");
```

### 10.3 Generating a session UUID

```javascript
const sessionId = crypto.randomUUID(); // Built into modern browsers — no library needed
```

### 10.4 Calling the streaming endpoint

```javascript
async function sendMessage(message) {
  const response = await fetch(`${serverUrl}/api/v1/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      project_id: projectId,
      widget_key: widgetKey,
    }),
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value);
    // Parse SSE format: "data: <token>\n\n"
    const token = chunk.replace(/^data: /, "").trim();
    appendToken(token); // Append each token to the chat bubble
  }
}
```

### 10.5 Reading config for widget appearance

The widget's color and greeting come from `.env` — but `widget.js` is
JavaScript and can't read `.env` directly. The backend needs to expose these
values. Add a config endpoint to `main.py`:

```python
@app.get("/api/v1/config")
def get_widget_config():
    from backend.config import (
        WIDGET_COLOR, GREETING_MESSAGE, QUICK_REPLIES, BUSINESS_NAME
    )
    return {
        "color": WIDGET_COLOR,
        "greeting": GREETING_MESSAGE,
        "quick_replies": QUICK_REPLIES,
        "business_name": BUSINESS_NAME,
    }
```

Fetch this in `widget.js` on load and apply the values to the UI.

### 10.6 Build `widget/index.html`

This is a test/demo page. It embeds the widget using the same `<script>` tag
that a real business would use:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>ChatForge Demo</title>
  </head>
  <body>
    <h1>ChatForge Widget Demo</h1>
    <p>The chat widget should appear in the bottom-right corner.</p>

    <script
      src="http://localhost:8000/widget.js"
      data-project-id="marios-pizza"
      data-widget-key="change-me-to-a-random-secret"
    ></script>
  </body>
</html>
```

Open this file in your browser to test the full end-to-end experience.

### ✅ Phase 10 Checkpoint

- [x] Opening `http://localhost:8000` shows the demo page with the chat bubble
- [x] Clicking the bubble opens the chat panel
- [x] Quick reply buttons appear and work
- [x] Typing a message and submitting shows a streaming reply
- [x] The widget colour matches `WIDGET_COLOR` in `.env`
- [x] Refreshing the page starts a new session (conversation history resets)

---

## Phase 11 — End-to-End Testing

**Goal:** Manually test every feature against the full checklist before
considering the build complete.

Work through each item — if anything fails, go back to the relevant phase.

### Backend

- [ ] `GET /health` → `{"status": "ok"}`
- [ ] `GET /api/v1/config` → returns color, greeting, quick_replies, business_name
- [ ] `POST /api/v1/chat` with valid credentials → `{"reply": "...", "mode": "ai"}`
- [ ] `POST /api/v1/chat` with wrong `project_id` → 401
- [ ] `POST /api/v1/chat` with wrong `widget_key` → 401
- [ ] `POST /api/v1/chat` with no `API_KEY` in `.env` → `{"mode": "fallback"}`
- [ ] `POST /api/v1/chat/stream` → tokens stream one by one
- [ ] Sending 4 messages quickly (with `RATE_LIMIT="3/minute"`) → 4th returns 429

### Memory

- [ ] Send "My name is Alex" then "What is my name?" in the same session → model answers correctly
- [ ] Same two messages with a different `session_id` → model has no context of name

### Widget

- [ ] Widget loads from `<script>` tag on the demo page
- [ ] Greeting message appears on open
- [ ] Quick reply buttons appear and send the correct message
- [ ] Streaming response renders token by token
- [ ] Widget colour matches config

### Fallback

- [ ] Remove `API_KEY` from `.env`, restart server
- [ ] Ask about hours → returns hours from config
- [ ] Ask about location → returns address from config
- [ ] Random gibberish → returns contact info

---

## Phase 12 — Deployment

**Goal:** Get ChatForge running on a public URL so a real business can embed it.

### 12.1 Choose a platform

Both are free to start and support Python:

- **Render** — https://render.com (easier, recommended for first deployment)
- **Railway** — https://railway.app (slightly more control)

### 12.2 Prepare for deployment

Make sure these are in your repository:

- `requirements.txt` with all dependencies
- `README.md` with the start command: `uvicorn backend.main:app --host 0.0.0.0 --port 8000`
- **Do not commit `.env`** — it contains secrets. Add it to `.gitignore` if it isn't already.

### 12.3 Set environment variables on the platform

On Render or Railway, go to the environment / variables section and add every
variable from your `.env` file one by one. Do not upload the `.env` file itself.

Set `ALLOWED_DOMAINS` to your actual deployment domain, e.g.
`yourbusiness.com,www.yourbusiness.com`.

### 12.4 Deploy

On Render: New → Web Service → connect your GitHub repo → set start command →
deploy.

The platform builds your app, installs dependencies from `requirements.txt`,
and starts the server.

### 12.5 Update the embed snippet

Once deployed, update the widget `<script>` tag with your live URL:

```html
<script
  src="https://your-app.onrender.com/widget.js"
  data-project-id="your-business-id"
  data-widget-key="your-random-secret"
></script>
```

### ✅ Phase 12 Checkpoint

- [ ] App is live at a public URL
- [ ] `https://your-app.onrender.com/health` returns `{"status": "ok"}`
- [ ] Widget embed works from a real webpage on your domain
- [ ] Requests from an unlisted domain are rejected with 403

---

## What's Next (Roadmap)

These features are not part of this build but are planned for future versions.
Once you've completed Phase 12, these are good stretch goals:

- [ ] Widget theme builder — let businesses pick colors and position via a UI
- [ ] One-click deploy button for Render / Railway
- [ ] Multi-language auto-detection — detect visitor language and respond in kind
- [ ] Business hours awareness — automatically tell visitors if the business is currently open or closed

---

## Quick Reference

| Command                                                                          | What it does                                       |
| -------------------------------------------------------------------------------- | -------------------------------------------------- |
| `source venv/bin/activate`                                                       | Activate virtual environment (Mac/Linux)           |
| `venv\Scripts\activate`                                                          | Activate virtual environment (Windows)             |
| `pip install -r requirements.txt`                                                | Install dependencies (must pin `langgraph==1.2.4`) |
| `uvicorn backend.main:app --reload`                                              | Start dev server with auto-reload                  |
| `python -c "from backend.config import *"`                                       | Smoke-test config loading                          |
| `python -c "from backend.memory import checkpointer; print(type(checkpointer))"` | Verify LangGraph checkpointer                      |

| URL                                        | What it is              |
| ------------------------------------------ | ----------------------- |
| `http://localhost:8000`                    | Widget demo page        |
| `http://localhost:8000/docs`               | Interactive API docs    |
| `http://localhost:8000/health`             | Health check            |
| `http://localhost:8000/api/v1/chat`        | Chat endpoint           |
| `http://localhost:8000/api/v1/chat/stream` | Streaming chat endpoint |
| `http://localhost:8000/api/v1/config`      | Widget config endpoint  |

| File                  | What you build in it                                        |
| --------------------- | ----------------------------------------------------------- |
| `backend/config.py`   | Phase 1 — env loader                                        |
| `backend/main.py`     | Phases 2, 4, 5, 9 — server, routes, security, rate limiting |
| `backend/fallback.py` | Phase 3 — rule-based NLP                                    |
| `backend/memory.py`   | Phase 6 — LangGraph MemorySaver checkpointer                |
| `backend/chat.py`     | Phase 7 — LangGraph AI integration                          |
| `widget/widget.js`    | Phase 10 — embeddable UI                                    |
| `widget/index.html`   | Phase 10 — demo/test page                                   |
