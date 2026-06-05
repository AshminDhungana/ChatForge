---

## Project Structure

```
chatforge/
├── docs/
│   ├── architecture.md  # How the project is built
│   └── install.md       # How to Setup
├── backend/
│   ├── main.py          # FastAPI app, routes, and rate limiting
│   ├── chat.py          # LangChain chat logic, streaming, and memory
│   ├── fallback.py      # Rule-based NLP fallback engine
│   ├── memory.py        # Per-session conversation memory manager
│   └── config.py        # Environment config loader
├── widget/
│   ├── widget.js        # Embeddable chat widget (streaming + quick replies)
│   └── index.html       # Widget demo and test page
├── .env.example         # Full configuration template
├── requirements.txt     # Python dependencies
├── LICENSE              # License
└── README.md            # Project documentation
```
