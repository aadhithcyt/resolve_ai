"""SQLite database setup and connection management."""
import sqlite3
import aiosqlite
from contextlib import asynccontextmanager
from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    company TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    subject TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','in_progress','resolved','closed')),
    priority TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN ('low','medium','high','urgent')),
    category TEXT DEFAULT 'general',
    sentiment TEXT CHECK(sentiment IN ('positive','neutral','negative')),
    ai_reply TEXT,
    assigned_to TEXT,
    sla_due_at TIMESTAMP,
    sla_breached BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    sender TEXT NOT NULL CHECK(sender IN ('customer','agent','system')),
    content TEXT NOT NULL,
    is_ai_generated BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_customer ON tickets(customer_id);
CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority);
CREATE INDEX IF NOT EXISTS idx_messages_ticket ON messages(ticket_id);

CREATE TABLE IF NOT EXISTS knowledge_base (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    tags TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_base_fts USING fts5(title, content, content='knowledge_base', content_rowid='id');

CREATE TABLE IF NOT EXISTS ai_analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    reply_text TEXT NOT NULL,
    tools_used TEXT,
    tool_calls_made INTEGER DEFAULT 0,
    reasoning TEXT,
    accepted BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);

CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'agent' CHECK(role IN ('admin','agent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


async def init_db():
    """Initialize database with schema and seed data."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()
    await seed_kb()


SEED_ARTICLES = [
    {
        "title": "How to Reset Your Password",
        "content": "To reset your password, go to the login page and click 'Forgot Password'. Enter your email address and we'll send you a reset link. The link expires in 24 hours.",
        "category": "account",
        "tags": "password,reset,login",
    },
    {
        "title": "Billing and Subscription FAQ",
        "content": "We offer monthly and annual billing plans. You can upgrade or downgrade your plan at any time from the billing section. Annual plans come with a 20% discount.",
        "category": "billing",
        "tags": "billing,subscription,payment",
    },
    {
        "title": "API Rate Limits and Best Practices",
        "content": "Our API allows 1000 requests per minute for standard plans. Use exponential backoff for retries. Include your API key in the Authorization header.",
        "category": "api",
        "tags": "api,rate-limits,best-practices",
    },
    {
        "title": "Troubleshooting Common Login Issues",
        "content": "If you can't log in, check that your email is correct, clear your browser cache, and ensure cookies are enabled. Try using an incognito window.",
        "category": "troubleshooting",
        "tags": "login,troubleshooting,cache",
    },
    {
        "title": "Setting Up Two-Factor Authentication",
        "content": "Enable 2FA in your account settings under Security. Scan the QR code with your authenticator app. Save your backup codes in a safe place.",
        "category": "security",
        "tags": "2fa,security,authentication",
    },
    {
        "title": "How to Contact Support",
        "content": "You can reach our support team via email at support@resolveai.com or through the in-app chat. Business hours are Monday to Friday, 9am to 6pm EST.",
        "category": "general",
        "tags": "support,contact,help",
    },
    {
        "title": "Data Export and Backup Options",
        "content": "Export your data in JSON or CSV format from the settings page. Automated daily backups are available on premium plans. Contact support for custom backup schedules.",
        "category": "data",
        "tags": "export,backup,data",
    },
    {
        "title": "Managing Team Members and Permissions",
        "content": "Invite team members from the Team Settings page. Assign roles: Admin, Agent, or Viewer. Admins can manage billing and team settings.",
        "category": "account",
        "tags": "team,permissions,roles",
    },
]


async def seed_kb():
    """Seed the knowledge base with sample articles if empty."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT COUNT(*) FROM knowledge_base")
        count = (await cursor.fetchone())[0]
        if count == 0:
            for article in SEED_ARTICLES:
                cursor = await db.execute(
                    "INSERT INTO knowledge_base (title, content, category, tags) VALUES (?, ?, ?, ?)",
                    (article["title"], article["content"], article["category"], article["tags"]),
                )
                await db.execute(
                    "INSERT INTO knowledge_base_fts(rowid, title, content) VALUES (?, ?, ?)",
                    (cursor.lastrowid, article["title"], article["content"]),
                )
            await db.commit()


@asynccontextmanager
async def get_db():
    """Async database connection context manager."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db
