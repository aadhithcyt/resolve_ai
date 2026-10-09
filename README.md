# ResolveAI — AI-Powered Customer Support Desk

A lightweight, professional customer support desk with AI-powered auto-replies, sentiment analysis, SLA tracking, and email notifications.

## Features

- **Ticket Management** — Create, view, update, and delete support tickets
- **Customer Management** — Full CRUD for customer records
- **AI Auto-Replies** — Generate contextual reply drafts using Groq LLM
- **Sentiment Analysis** — Automatic sentiment tagging on incoming messages
- **SLA Tracking** — Automatic SLA due dates by priority, breach detection, and filtering
- **Email Notifications** — Optional SMTP alerts for new tickets, SLA breaches, and resolutions
- **Dashboard** — Real-time stats, metrics, SLA breach count, and recent activity
- **Conversation Threads** — Full message history per ticket
- **Search & Filter** — Find tickets by status, priority, category, keyword, or SLA breach
- **API Key Auth** — Optional X-API-Key header authentication
- **Rate Limiting** — Sliding window + burst rate limiter per client
- **Docker Support** — Dockerfile and docker-compose.yml included
- **CI/CD** — GitHub Actions workflow for testing on Python 3.10–3.13

## Tech Stack

| Layer     | Technology                          |
|-----------|-------------------------------------|
| Backend   | Python 3.10+ / FastAPI              |
| Database  | SQLite (via aiosqlite)              |
| AI        | Groq API (openai/gpt-oss-120b)      |
| Email     | aiosmtplib (optional)               |
| Frontend  | Vanilla HTML/CSS/JS (no build step) |
| Server    | Uvicorn                             |

## Quick Start

### Prerequisites

- Python 3.10+
- A [Groq API key](https://console.groq.com/keys) (free tier available)

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/resolveai.git
cd resolveai
chmod +x setup.sh
./setup.sh
```

### Configuration

Set your Groq API key:

```bash
export GROQ_API_KEY="your-key-here"
```

Optional environment variables:

| Variable            | Default                        | Description              |
|---------------------|--------------------------------|--------------------------|
| `GROQ_API_KEY`      | (required for AI features)     | Groq API key             |
| `RESOLVEAI_DB`      | `./resolveai.db`               | SQLite database path     |
| `RESOLVEAI_MODEL`   | `openai/gpt-oss-120b`          | Groq model to use        |
| `RESOLVEAI_HOST`    | `127.0.0.1`                    | Server bind address      |
| `RESOLVEAI_PORT`    | `8000`                         | Server port              |
| `RESOLVEAI_DEBUG`   | `false`                        | Enable debug mode        |
| `RESOLVEAI_API_KEY` | (empty = auth disabled)        | API key for X-API-Key    |
| `RATE_LIMIT_RPM`    | `60`                           | Requests per minute      |
| `RATE_LIMIT_BURST`  | `10`                           | Burst capacity           |
| `EMAIL_HOST`        | (empty = email disabled)       | SMTP host                |
| `EMAIL_PORT`        | `587`                          | SMTP port                |
| `EMAIL_USER`        | (empty)                        | SMTP username            |
| `EMAIL_PASSWORD`    | (empty)                        | SMTP password            |
| `EMAIL_FROM`        | `noreply@resolveai.local`       | From address             |
| `EMAIL_TO`          | (empty)                        | To address               |

### Run

```bash
./run.sh
```

Or manually:

```bash
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 in your browser.

### Docker

```bash
docker-compose up -d
```

Or with Docker directly:

```bash
docker build -t resolveai .
docker run -p 8000:8000 -e GROQ_API_KEY=your-key resolveai
```

## API Endpoints

All endpoints (except `/health`) require `X-API-Key` header when `RESOLVEAI_API_KEY` is set.

### Tickets
- `POST /api/tickets/` — Create ticket
- `GET /api/tickets/` — List tickets (with filters: status, priority, category, customer_id, search, sla_breached)
- `GET /api/tickets/{id}` — Get ticket details
- `PUT /api/tickets/{id}` — Update ticket
- `DELETE /api/tickets/{id}` — Delete ticket
- `GET /api/tickets/{id}/messages` — Get conversation
- `POST /api/tickets/{id}/messages` — Add message
- `GET /api/tickets/{id}/sla` — Get SLA details

### Customers
- `POST /api/customers/` — Create customer
- `GET /api/customers/` — List customers
- `GET /api/customers/{id}` — Get customer
- `PUT /api/customers/{id}` — Update customer
- `DELETE /api/customers/{id}` — Delete customer

### AI
- `POST /api/ai/reply` — Generate AI reply for a ticket
- `POST /api/ai/sentiment/{ticket_id}` — Analyze ticket sentiment

### Dashboard
- `GET /api/dashboard/stats` — Get dashboard statistics (includes SLA breach count)

### Health
- `GET /health` — Health check (no auth required)

## SLA Targets

| Priority | SLA Target |
|----------|------------|
| Low      | 72 hours   |
| Medium   | 48 hours   |
| High     | 24 hours   |
| Urgent   | 4 hours    |

SLA is computed at ticket creation and recomputed when priority changes. Breached tickets are flagged automatically.

## Project Structure

```
resolveai/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Settings
│   ├── database.py          # SQLite setup
│   ├── models.py            # Pydantic schemas
│   ├── ai.py                # Groq AI integration
│   ├── auth.py              # API key auth + rate limiting
│   ├── email.py             # Email notifications
│   ├── routers/
│   │   ├── tickets.py       # Ticket routes (with SLA)
│   │   ├── customers.py     # Customer routes
│   │   ├── ai_assist.py     # AI routes
│   │   └── dashboard.py     # Stats routes
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/app.js
│   └── templates/
│       └── index.html
├── tests/
│   ├── conftest.py
│   ├── test_tickets.py
│   ├── test_customers.py
│   ├── test_ai.py
│   ├── test_sla.py
│   └── test_auth.py
├── .github/
│   └── workflows/ci.yml
├── requirements.txt
├── setup.sh
├── run.sh
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Running Tests

```bash
pip install pytest pytest-asyncio httpx
pytest tests/ -v
```

28 tests covering tickets, customers, AI, SLA, auth, and rate limiting.

## CI/CD

GitHub Actions workflow runs on every push/PR to main/master:
- Tests on Python 3.10, 3.11, 3.12, 3.13
- Syntax check on all modules

## License

MIT
