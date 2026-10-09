# ResolveAI — AI-Powered Customer Support Desk

A lightweight, professional customer support desk with AI-powered auto-replies and sentiment analysis.

## Features

- **Ticket Management** — Create, view, update, and delete support tickets
- **Customer Management** — Full CRUD for customer records
- **AI Auto-Replies** — Generate contextual reply drafts using Groq LLM
- **Sentiment Analysis** — Automatic sentiment tagging on incoming messages
- **Dashboard** — Real-time stats, metrics, and recent activity
- **Conversation Threads** — Full message history per ticket
- **Search & Filter** — Find tickets by status, priority, category, or keyword

## Tech Stack

| Layer     | Technology                          |
|-----------|-------------------------------------|
| Backend   | Python 3.10+ / FastAPI              |
| Database  | SQLite (via aiosqlite)              |
| AI        | Groq API (llama-3.3-70b-versatile)  |
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

## API Endpoints

### Tickets
- `POST /api/tickets/` — Create ticket
- `GET /api/tickets/` — List tickets (with filters)
- `GET /api/tickets/{id}` — Get ticket details
- `PUT /api/tickets/{id}` — Update ticket
- `DELETE /api/tickets/{id}` — Delete ticket
- `GET /api/tickets/{id}/messages` — Get conversation
- `POST /api/tickets/{id}/messages` — Add message

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
- `GET /api/dashboard/stats` — Get dashboard statistics

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
│   ├── routers/
│   │   ├── tickets.py       # Ticket routes
│   │   ├── customers.py     # Customer routes
│   │   ├── ai_assist.py     # AI routes
│   │   └── dashboard.py     # Stats routes
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/app.js
│   └── templates/
│       └── index.html
├── tests/
│   ├── test_tickets.py
│   ├── test_customers.py
│   └── test_ai.py
├── requirements.txt
├── setup.sh
├── run.sh
└── README.md
```

## Running Tests

```bash
pip install pytest pytest-asyncio httpx
pytest tests/ -v
```

## License

MIT
