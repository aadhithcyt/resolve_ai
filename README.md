# ResolveAI — AI-Powered Customer Support Desk

A production-ready customer support platform with AI-powered auto-replies, streaming agent interactions, SLA tracking, real-time collaboration, and a beautiful, color-psychology-driven interface.

## Features

### AI Agent (Core)
- Multi-turn tool calling with 5 tools (get_ticket_info, get_customer_info, search_knowledge_base, escalate_ticket, add_ticket_note)
- Streaming SSE output with live tool call visualization and typing animation
- Conversation memory — remembers past interactions with customers
- Auto-triage — AI classifies category and priority automatically
- AI analytics — reply tracking, acceptance rate, tool usage statistics

### Ticket Management
- Full CRUD with search, filter (status, priority, category, keyword, SLA breach)
- SLA tracking with automatic due dates by priority (urgent 4h, high 24h, medium 48h, low 72h)
- Escalation engine with 4 automatic rules
- File attachments (upload, download, delete)
- Conversation threads with real-time WebSocket chat
- Drag-and-drop ticket assignment to agents
- Collaborative AI reply editing

### Customer Management
- Full CRUD with email uniqueness
- Customer portal (public API for ticket status by email)

### Knowledge Base
- CRUD with FTS5 full-text search
- 8 sample articles pre-loaded on first run
- AI agent searches KB before drafting replies

### Notifications
- Email (SMTP) for new tickets, SLA breaches, resolutions
- Webhooks to Slack, Discord, Teams
- Browser push notifications (Service Worker)
- Real-time SSE updates in dashboard

### Collaboration
- Real-time multi-agent presence (online indicator)
- Team @mentions with internal notes
- Real-time customer chat (WebSocket)
- Command palette (Ctrl+K) for quick navigation

### Platform
- Windows, Linux, macOS support
- Docker and docker-compose
- CI/CD with GitHub Actions (Python 3.10–3.13)
- 197 tests covering all modules

## Quick Start

### Windows
```cmd
git clone https://github.com/YOUR_USERNAME/resolveai.git
cd resolveai
setup.bat
set GROQ_API_KEY=your-key-here
run.bat
```

### Linux / macOS / RHEL
```bash
git clone https://github.com/YOUR_USERNAME/resolveai.git
cd resolveai
chmod +x setup.sh
./setup.sh
export GROQ_API_KEY=your-key-here
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Docker
```bash
docker build -t resolveai .
docker run -p 8000:8000 -e GROQ_API_KEY=your-key resolveai
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | Yes | — | Groq API key |
| `RESOLVEAI_JWT_SECRET` | Recommended | Random | JWT signing secret |
| `RESOLVEAI_API_KEY` | Recommended | — | API key for X-API-Key auth |
| `RESOLVEAI_MODEL` | No | `openai/gpt-oss-120b` | Groq model |
| `RESOLVEAI_HOST` | No | `127.0.0.1` | Server bind address |
| `RESOLVEAI_PORT` | No | `8000` | Server port |
| `RATE_LIMIT_RPM` | No | `60` | Requests per minute |
| `RATE_LIMIT_BURST` | No | `10` | Burst capacity |
| `EMAIL_HOST` | No | — | SMTP host |
| `EMAIL_PORT` | No | `587` | SMTP port |

See `.env.example` for the full list.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+ / FastAPI |
| Database | SQLite (aiosqlite + FTS5) |
| AI | Groq API (openai/gpt-oss-120b) |
| Auth | JWT (PyJWT) + bcrypt |
| Real-time | SSE + WebSocket |
| Frontend | Vanilla HTML/CSS/JS |
| Server | Uvicorn |

## Project Structure

```
resolveai/
├── app/
│   ├── agent.py              # AI agent loop with tool calling
│   ├── agent_router.py       # Agent API endpoint
│   ├── analytics.py          # AI performance tracking
│   ├── attachments.py        # File upload/download
│   ├── auth.py               # API key + JWT middleware
│   ├── cache.py              # In-memory response cache
│   ├── chat.py               # WebSocket real-time chat
│   ├── config.py             # Settings
│   ├── database.py           # SQLite schema + FTS5
│   ├── email.py              # Email notifications
│   ├── escalation.py         # Auto-escalation rules
│   ├── i18n.py               # Multi-language support
│   ├── import_export.py      # JSON/CSV import/export
│   ├── jwt_auth.py           # JWT login/register
│   ├── main.py               # FastAPI app entry
│   ├── memory.py             # Conversation memory
│   ├── models.py             # Pydantic schemas
│   ├── notifications.py      # Browser push notifications
│   ├── portal.py           # Customer portal (public API)
│   ├── presence.py           # Agent online presence
│   ├── sse.py                # Server-Sent Events streaming
│   ├── team.py               # @mentions and internal notes
│   ├── tools.py              # Tool definitions + executor
│   ├── triage.py             # AI auto-classification
│   ├── webhook.py            # Slack/Discord/Teams webhooks
│   ├── workers.py            # Background workers (SLA + email)
│   ├── routers/              # Ticket, customer, KB, dashboard routes
│   ├── static/               # CSS + JS frontend
│   └── templates/            # HTML templates
├── public/
│   └── sw.js                 # Service worker for push notifications
├── tests/                    # 197 tests
├── setup.sh / setup.bat      # Cross-platform setup
├── run.sh / run.bat          # Cross-platform run
├── Dockerfile
├── docker-compose.yml
├── DEPLOYMENT.md             # RHEL/Windows deployment guide
├── requirements.txt
└── README.md
```

## Security

- bcrypt password hashing
- JWT with 24-hour expiry
- Timing-safe API key comparison
- Parameterized SQL queries (no injection)
- Pydantic input validation
- Rate limiting (sliding window + burst)
- File upload type whitelist + size limit
- Security headers (X-Frame-Options, X-Content-Type-Options, etc.)
- Role-based access control (admin/agent)

## Testing

```bash
pip install pytest pytest-asyncio httpx
pytest tests/ -v
```

197 tests covering tickets, customers, AI agent, SLA, auth, KB, attachments, memory, streaming, notifications, presence, chat, and platform compatibility.

## License

MIT
