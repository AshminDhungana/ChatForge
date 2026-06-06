---

## Project Structure

```
chatforge/
├── docs/
│   ├── architecture.md    # System design and folder structure
│   ├── install.md         # Setup and installation guide
│   ├── todo.md            # Project roadmap and pending tasks
│   └── user_guide.md      # User documentation for the chat widget
├── backend/
│   ├── main.py            # FastAPI application entry point and API routes
│   ├── chat.py            # LangChain integration and chat orchestration
│   ├── ai_health.py       # AI availability monitoring and auto-recovery
│   ├── fallback.py        # Rule-based NLP engine for AI failover
│   ├── memory.py          # Session-based conversation history management
│   ├── models.py          # Pydantic data models for API requests/responses
│   ├── config.py         # Environment variables and system configuration
│   └── static/            # Static assets (e.g., favicon)
├── widget/
│   ├── widget.js          # Embeddable chat widget frontend logic
│   └── index.html         # Widget demonstration and testing page
├── .env.example           # Template for environment configuration
├── requirements.txt       # Python project dependencies
├── LICENSE                # Project license
└── README.md              # Project overview and quick start
```
