<div align="center">

<br/>

# ChatForge

**Plug-and-play AI chatbot platform for local and small businesses.**

ChatForge is a lightweight, embeddable chatbot powered by LangChain and any OpenAI-compatible API. Drop it onto any website in minutes — no complex setup, no vendor lock-in.

<br/>

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=flat-square&logo=langchain&logoColor=white)](https://langchain.com)
[![Python 3.10+](https://img.shields.io/badge/Python_3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)
[![OpenAI Compatible](https://img.shields.io/badge/OpenAI-Compatible-412991?style=flat-square&logo=openai&logoColor=white)](https://openai.com)

[Getting Started](#setup--installation) · [Configuration](#configuration) · [API Reference](#api-reference) · [Providers](#supported-ai-providers) · [Roadmap](#roadmap)

</div>

---

## Overview

ChatForge gives any business a production-ready AI chatbot with a single line of HTML. It handles conversation memory, streaming responses, session isolation, and graceful fallback — all configurable through a single `.env` file.

---

## Features

| Feature                 | Description                                                                        |
| ----------------------- | ---------------------------------------------------------------------------------- |
| **AI Chat**             | Works with any OpenAI-compatible API — Groq, OpenAI, Together AI, Ollama, and more |
| **Streaming Responses** | Real-time token streaming for an instant, ChatGPT-style experience                 |
| **Conversation Memory** | Retains full context within each visitor session                                   |
| **Quick Reply Buttons** | Configurable shortcut buttons for your most common customer questions              |
| **Smart Fallback**      | Rule-based NLP engine activates automatically when no API key is configured        |
| **Rate Limiting**       | Per-session request throttling to protect API usage and control costs              |
| **Session Isolation**   | Each visitor receives a unique session ID — no memory bleed between users          |
| **Brand Customization** | Configure widget color, greeting message, and style to match your business         |
| **Embeddable Widget**   | A single `<script>` tag — works on any website or platform                         |
| **Privacy First**       | Business owners supply their own API keys — ChatForge stores no data               |

---

## Tech Stack

| Layer             | Technology                        | Purpose                                         |
| ----------------- | --------------------------------- | ----------------------------------------------- |
| **Backend**       | FastAPI + Uvicorn                 | High-performance async API server               |
| **AI Layer**      | LangChain + ChatOpenAI            | Unified interface for any OpenAI-compatible LLM |
| **Streaming**     | `StreamingResponse` + `astream()` | Real-time token delivery                        |
| **Memory**        | `ConversationBufferMemory`        | In-session conversation context                 |
| **Rate Limiting** | SlowAPI                           | Per-session abuse prevention                    |
| **Fallback**      | Rule-based NLP engine             | Always-on responses without an API key          |
| **Widget**        | Vanilla JavaScript                | Zero-dependency embeddable chat UI              |
| **Config**        | `.env` + python-dotenv            | Single-file business configuration              |

---

## Setup & Installation

### 1. Clone the repository

```bash
git clone https://github.com/AshminDhungana/chatforge.git
cd chatforge
```

### 2. Install dependencies

> Requires **Python 3.10 or higher**.

```bash
pip install -r requirements.txt
```

### 3. Configure your environment

```bash
cp .env.example .env
```

Edit `.env` with your business details — see [Configuration](#configuration) below.

### 4. Start the server

```bash
uvicorn backend.main:app --reload
```

The server runs at `http://localhost:8000`. Interactive API docs are available at `http://localhost:8000/docs`.

### 5. Embed the widget

Add this single line to any page's HTML:

```html
<script
  src="http://localhost:8000/widget.js"
  data-project-id="marios-pizza"
  data-widget-key="your-random-secret"
></script>
```

The widget loads automatically — no additional setup required.

---

## Configuration

Copy `.env.example` to `.env` and fill in your details:

| Variable               | Required | Description                                                                           |
| ---------------------- | -------- | ------------------------------------------------------------------------------------- |
| `BUSINESS_NAME`        | Yes      | Your business name, used in chatbot responses                                         |
| `BUSINESS_DESCRIPTION` | Yes      | Short description of what your business does                                          |
| `BUSINESS_HOURS`       | Yes      | Opening hours, e.g. `Mon–Sat 9AM–10PM, Sun 11AM–9PM`                                  |
| `BUSINESS_PHONE`       | Yes      | Contact phone number                                                                  |
| `BUSINESS_ADDRESS`     | Yes      | Physical address                                                                      |
| `BUSINESS_WEBSITE`     | Yes      | Your website URL                                                                      |
| `PROJECT_ID`           | Yes      | Unique identifier for this chatbot instance, e.g. `marios-pizza`                      |
| `ALLOWED_DOMAINS`      | Yes      | Comma-separated list of domains allowed to embed the widget                           |
| `WIDGET_API_KEY`       | No       | Secret key for widget authentication — recommended for production                     |
| `QUICK_REPLIES`        | No       | Comma-separated shortcut button labels shown at chat start                            |
| `API_KEY`              | No       | Your LLM provider API key — leave blank to use the fallback engine                    |
| `API_BASE`             | No       | Base URL of your LLM provider — see [Supported AI Providers](#supported-ai-providers) |
| `MODEL`                | No       | Model name to use, e.g. `llama3-8b-8192`                                              |
| `WIDGET_COLOR`         | No       | Hex color for the chat widget, e.g. `#2563EB`                                         |
| `GREETING_MESSAGE`     | No       | First message shown to visitors when the widget opens                                 |
| `RATE_LIMIT`           | No       | Max requests per session per minute, e.g. `20/minute` (default: `20/minute`)          |

---

## Widget Security

ChatForge supports lightweight widget authentication without requiring a database.

Configure the following variables:

```env
PROJECT_ID="marios-pizza"
ALLOWED_DOMAINS="mariospizza.com,www.mariospizza.com"
WIDGET_API_KEY="your-random-secret"
```

The backend validates:

- Project ID
- Widget API key (if configured)
- Origin header
- Referer header
- Allowed domains

`WIDGET_API_KEY` is optional but strongly recommended for production. Requests from unauthorized websites are automatically rejected.

---

## API Reference

### Chat

```http
POST /api/v1/chat
```

**Request body:**

```json
{
  "message": "What are your opening hours?",
  "session_id": "uuid-per-visitor",
  "project_id": "marios-pizza",
  "widget_key": "your-random-secret"
}
```

**Response:**

```json
{
  "reply": "We are open Mon–Sat 9AM–10PM, Sun 11AM–9PM.",
  "mode": "ai"
}
```

### Streaming chat

```http
POST /api/v1/chat/stream
```

Returns a `text/event-stream`. Tokens are streamed in real time to the widget.

### Response modes

| Mode       | Trigger            | Description                               |
| ---------- | ------------------ | ----------------------------------------- |
| `ai`       | API key configured | Full LangChain + LLM response with memory |
| `fallback` | No API key         | Rule-based NLP keyword matching           |

---

## Supported AI Providers

Any OpenAI-compatible API works out of the box. Set `API_BASE` in your `.env`:

| Provider        | API Base URL                     | Cost         | Speed    |
| --------------- | -------------------------------- | ------------ | -------- |
| **OpenAI**      | `https://api.openai.com/v1`      | Paid         | ⚡⚡⚡   |
| **Groq**        | `https://api.groq.com/openai/v1` | Free tier    | ⚡⚡⚡⚡ |
| **Together AI** | `https://api.together.xyz/v1`    | Free tier    | ⚡⚡⚡   |
| **OpenRouter**  | `https://openrouter.ai/api/v1`   | Pay per use  | ⚡⚡⚡   |
| **Ollama**      | `http://localhost:11434/v1`      | Free (local) | ⚡⚡     |

> **Recommended for small businesses:** Groq — free, extremely fast, and no credit card required to start.

---

## How It Works

### Streaming responses

Tokens are sent to the widget in real time using LangChain's `astream()` and FastAPI's `StreamingResponse`, rather than waiting for the full reply to complete. The result feels instant.

### Conversation memory

Each visitor session gets its own `ConversationBufferMemory` instance. The bot remembers earlier messages within the same chat. Memory is scoped to the session and cleared when the visitor leaves.

### Session isolation

The widget generates a unique UUID per visitor on load. Two visitors chatting simultaneously never share or mix conversation history.

### Quick reply buttons

Configurable shortcut buttons appear at the start of the chat. Visitors can tap them instead of typing — useful for common questions like hours, location, and contact info.

### Rate limiting

Each session is limited to a configurable number of requests per minute (default: `20/minute`) via `slowapi`. This prevents abuse and protects API usage costs. Adjust with the `RATE_LIMIT` variable in `.env`.

### Fallback engine

When no API key is set, ChatForge silently switches to a lightweight rule-based engine:

```
Visitor sends a message
        ↓
No API key detected
        ↓
Keyword matching runs
        ↓
FAQ-style answer returned
        ↓
No match → shows business contact info
```

The chatbot is always online, even with no AI configuration.

---

## Requirements

- **Python 3.10 or higher**
- An OpenAI-compatible API key (optional — the fallback engine works without one)
- For Ollama: a locally running Ollama instance at `http://localhost:11434`

Install all Python dependencies:

```bash
pip install -r requirements.txt
```

---

## Roadmap

**Shipped**

- [x] FastAPI backend with Uvicorn
- [x] LangChain integration with any OpenAI-compatible API
- [x] NLP fallback engine
- [x] Embeddable Vanilla JS widget
- [x] Streaming responses
- [x] Per-session conversation memory
- [x] Session isolation via UUID
- [x] Configurable quick reply buttons
- [x] Per-session rate limiting
- [x] Full `.env` configuration with all provider URLs

**Coming Soon**

- [ ] Widget theme builder (colors, position, avatar)
- [ ] One-click deploy (Railway / Render)
- [ ] Multi-language auto-detection
- [ ] Business hours awareness

---

## Contributing

Contributions are welcome.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m 'Add your feature'`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a pull request

For significant changes, please open an issue first to discuss what you'd like to change.

---

## License

Released under the [MIT License](LICENSE).

---

## Support

Having trouble? Open an [issue on GitHub](https://github.com/AshminDhungana/chatforge/issues).

---

<div align="center">

Made with care for local businesses everywhere.

</div>
