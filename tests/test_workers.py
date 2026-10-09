"""Tests for background workers: SLA breach scanner and email receiver."""
import asyncio
import email
import imaplib
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import aiosqlite

from app.workers import (
    sla_breach_scanner,
    email_receiver,
    start_workers,
    stop_workers,
    _find_sla_breached_tickets,
    _mark_sla_breached,
    _send_sla_breach_notification,
    _fetch_unseen_emails,
    _create_ticket_from_email,
    _find_customer_by_email,
    SLA_SCAN_INTERVAL,
    EMAIL_POLL_INTERVAL,
)
from app.config import DB_PATH


@pytest_asyncio.fixture
async def setup_breached_ticket():
    """Create a ticket that is past SLA due date and still open."""
    from app.database import init_db
    await init_db()

    # Create customer
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO customers (name, email) VALUES (?, ?)",
            ("SLA Test Customer", "sla@test.com"),
        )
        customer_id = cursor.lastrowid
        await db.commit()

    # Create ticket with SLA due in the past
    past_due = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO tickets (customer_id, subject, description, status, priority, sla_due_at, sla_breached)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (customer_id, "Breached ticket", "Test description", "open", "high", past_due, 0),
        )
        ticket_id = cursor.lastrowid
        await db.commit()

    yield {"ticket_id": ticket_id, "customer_id": customer_id}

    # Cleanup
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
        await db.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        await db.commit()


@pytest_asyncio.fixture
async def setup_resolved_ticket():
    """Create a resolved ticket past SLA (should NOT be flagged)."""
    from app.database import init_db
    await init_db()

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO customers (name, email) VALUES (?, ?)",
            ("Resolved Customer", "resolved@test.com"),
        )
        customer_id = cursor.lastrowid
        await db.commit()

    past_due = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO tickets (customer_id, subject, description, status, priority, sla_due_at, sla_breached)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (customer_id, "Resolved ticket", "Test", "resolved", "high", past_due, 0),
        )
        ticket_id = cursor.lastrowid
        await db.commit()

    yield {"ticket_id": ticket_id, "customer_id": customer_id}

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
        await db.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        await db.commit()


@pytest.mark.asyncio
async def test_find_sla_breached_tickets(setup_breached_ticket):
    """Should find tickets past SLA that are still open."""
    tickets = await _find_sla_breached_tickets()
    assert len(tickets) >= 1
    ticket_ids = [t["id"] for t in tickets]
    assert setup_breached_ticket["ticket_id"] in ticket_ids


@pytest.mark.asyncio
async def test_find_sla_breached_excludes_resolved(setup_resolved_ticket):
    """Should NOT find resolved tickets even if past SLA."""
    tickets = await _find_sla_breached_tickets()
    ticket_ids = [t["id"] for t in tickets]
    assert setup_resolved_ticket["ticket_id"] not in ticket_ids


@pytest.mark.asyncio
async def test_mark_sla_breached(setup_breached_ticket):
    """Should mark a ticket as SLA breached."""
    await _mark_sla_breached(setup_breached_ticket["ticket_id"])

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT sla_breached FROM tickets WHERE id = ?",
            (setup_breached_ticket["ticket_id"],),
        )
        row = await cursor.fetchone()
        assert row["sla_breached"] == 1


@pytest.mark.asyncio
async def test_send_sla_breach_notification(setup_breached_ticket):
    """Should send SLA breach notification email."""
    ticket = {
        "id": setup_breached_ticket["ticket_id"],
        "subject": "Test subject",
        "customer_name": "Test Customer",
        "priority": "high",
        "sla_due_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
    }

    with patch("app.workers.notify_sla_breach", new=AsyncMock(return_value=True)) as mock_notify:
        result = await _send_sla_breach_notification(ticket)
        assert result is True
        mock_notify.assert_called_once()
        call_kwargs = mock_notify.call_args
        assert call_kwargs.kwargs["ticket_id"] == ticket["id"]
        assert call_kwargs.kwargs["subject"] == ticket["subject"]


@pytest.mark.asyncio
async def test_sla_breach_scanner_marks_and_notifies(setup_breached_ticket):
    """Scanner should find, mark, and notify for breached tickets."""
    with patch("app.workers._send_sla_breach_notification", new=AsyncMock(return_value=True)) as mock_notify:
        # Run scanner once by setting stop_event after first iteration
        stop_event = asyncio.Event()

        async def run_scanner():
            await sla_breach_scanner(stop_event)

        task = asyncio.create_task(run_scanner())
        # Give it time to run one iteration
        await asyncio.sleep(0.5)
        stop_event.set()
        await task

    # Verify ticket was marked as breached
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT sla_breached FROM tickets WHERE id = ?",
            (setup_breached_ticket["ticket_id"],),
        )
        row = await cursor.fetchone()
        assert row["sla_breached"] == 1

    # Verify notification was sent
    mock_notify.assert_called_once()


@pytest.mark.asyncio
async def test_sla_breach_scanner_no_breaches(setup_resolved_ticket):
    """Scanner should not flag resolved tickets."""
    with patch("app.workers._send_sla_breach_notification", new=AsyncMock(return_value=True)) as mock_notify:
        stop_event = asyncio.Event()

        async def run_scanner():
            await sla_breach_scanner(stop_event)

        task = asyncio.create_task(run_scanner())
        await asyncio.sleep(0.5)
        stop_event.set()
        await task

    mock_notify.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_unseen_emails_not_configured():
    """Should return empty list when IMAP not configured."""
    with patch("app.workers.EMAIL_HOST", ""), patch("app.workers.EMAIL_USER", ""):
        result = await _fetch_unseen_emails()
        assert result == []


@pytest.mark.asyncio
async def test_fetch_unseen_emails_imap_error():
    """Should handle IMAP errors gracefully."""
    with patch("app.workers.EMAIL_HOST", "imap.test.com"), \
         patch("app.workers.EMAIL_USER", "test@test.com"), \
         patch("app.workers.EMAIL_PASSWORD", "pass"), \
         patch("app.workers._imap_fetch_unseen", side_effect=Exception("Connection failed")):
        result = await _fetch_unseen_emails()
        assert result == []


@pytest.mark.asyncio
async def test_create_ticket_from_email_new_customer():
    """Should create ticket and customer from email."""
    email_data = {
        "subject": "Help needed",
        "from": "newcustomer@test.com",
        "from_header": "New Customer <newcustomer@test.com>",
        "body": "I need help with my account",
        "message_id": "<test123@test.com>",
    }

    with patch("app.workers.send_email", new=AsyncMock(return_value=True)):
        ticket = await _create_ticket_from_email(email_data)

    assert ticket is not None
    assert ticket["subject"] == "Help needed"
    assert ticket["customer_id"] is not None

    # Verify customer was created
    customer = await _find_customer_by_email("newcustomer@test.com")
    assert customer is not None
    assert customer["email"] == "newcustomer@test.com"

    # Cleanup
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM tickets WHERE id = ?", (ticket["id"],))
        await db.execute("DELETE FROM customers WHERE email = ?", ("newcustomer@test.com",))
        await db.commit()


@pytest.mark.asyncio
async def test_create_ticket_from_email_existing_customer():
    """Should create ticket for existing customer."""
    # Create customer first
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO customers (name, email) VALUES (?, ?)",
            ("Existing Customer", "existing@test.com"),
        )
        customer_id = cursor.lastrowid
        await db.commit()

    email_data = {
        "subject": "Another issue",
        "from": "existing@test.com",
        "from_header": "Existing Customer <existing@test.com>",
        "body": "I have another problem",
        "message_id": "<test456@test.com>",
    }

    with patch("app.workers.send_email", new=AsyncMock(return_value=True)):
        ticket = await _create_ticket_from_email(email_data)

    assert ticket is not None
    assert ticket["customer_id"] == customer_id
    assert ticket["subject"] == "Another issue"

    # Cleanup
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM tickets WHERE id = ?", (ticket["id"],))
        await db.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        await db.commit()


@pytest.mark.asyncio
async def test_create_ticket_from_email_no_sender():
    """Should skip emails with no sender."""
    email_data = {
        "subject": "No sender",
        "from": "",
        "from_header": "",
        "body": "Test body",
    }

    ticket = await _create_ticket_from_email(email_data)
    assert ticket is None


@pytest.mark.asyncio
async def test_email_receiver_creates_tickets():
    """Email receiver should fetch emails and create tickets."""
    mock_emails = [
        {
            "subject": "Test email ticket",
            "from": "emailtest@test.com",
            "from_header": "Email Test <emailtest@test.com>",
            "body": "This is a test email body",
            "message_id": "<emailtest@test.com>",
        }
    ]

    with patch("app.workers._fetch_unseen_emails", new=AsyncMock(return_value=mock_emails)), \
         patch("app.workers.send_email", new=AsyncMock(return_value=True)):
        stop_event = asyncio.Event()

        async def run_receiver():
            await email_receiver(stop_event)

        task = asyncio.create_task(run_receiver())
        await asyncio.sleep(0.5)
        stop_event.set()
        await task

    # Verify ticket was created
    customer = await _find_customer_by_email("emailtest@test.com")
    assert customer is not None

    # Cleanup
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM tickets WHERE customer_id = ?", (customer["id"],))
        await db.execute("DELETE FROM customers WHERE id = ?", (customer["id"],))
        await db.commit()


@pytest.mark.asyncio
async def test_email_receiver_no_emails():
    """Email receiver should handle no new emails gracefully."""
    with patch("app.workers._fetch_unseen_emails", new=AsyncMock(return_value=[])):
        stop_event = asyncio.Event()

        async def run_receiver():
            await email_receiver(stop_event)

        task = asyncio.create_task(run_receiver())
        await asyncio.sleep(0.5)
        stop_event.set()
        await task
    # No assertion needed - just verifying no crash


@pytest.mark.asyncio
async def test_start_and_stop_workers():
    """Should start and stop workers without errors."""
    tasks = await start_workers()
    assert len(tasks) == 2
    assert all(isinstance(t, asyncio.Task) for t in tasks)

    # Let them run briefly
    await asyncio.sleep(0.1)

    await stop_workers()

    # All tasks should be done
    for task in tasks:
        assert task.done()


@pytest.mark.asyncio
async def test_sla_scan_interval():
    """SLA scan interval should be 5 minutes (300 seconds)."""
    assert SLA_SCAN_INTERVAL == 300


@pytest.mark.asyncio
async def test_email_poll_interval():
    """Email poll interval should be 60 seconds."""
    assert EMAIL_POLL_INTERVAL == 60


@pytest.mark.asyncio
async def test_find_customer_by_email_not_found():
    """Should return None for non-existent customer."""
    result = await _find_customer_by_email("nonexistent@test.com")
    assert result is None


@pytest.mark.asyncio
async def test_sla_breach_scanner_handles_db_error():
    """Scanner should handle database errors gracefully."""
    with patch("app.workers._find_sla_breached_tickets", side_effect=Exception("DB error")):
        stop_event = asyncio.Event()

        async def run_scanner():
            await sla_breach_scanner(stop_event)

        task = asyncio.create_task(run_scanner())
        await asyncio.sleep(0.5)
        stop_event.set()
        await task
    # No assertion needed - just verifying no unhandled exception


@pytest.mark.asyncio
async def test_email_receiver_handles_email_error():
    """Receiver should handle errors when creating tickets from emails."""
    mock_emails = [
        {
            "subject": "Bad email",
            "from": "bad@test.com",
            "from_header": "Bad <bad@test.com>",
            "body": "Test",
            "message_id": "<bad@test.com>",
        }
    ]

    with patch("app.workers._fetch_unseen_emails", new=AsyncMock(return_value=mock_emails)), \
         patch("app.workers._create_ticket_from_email", side_effect=Exception("Create error")):
        stop_event = asyncio.Event()

        async def run_receiver():
            await email_receiver(stop_event)

        task = asyncio.create_task(run_receiver())
        await asyncio.sleep(0.5)
        stop_event.set()
        await task
    # No assertion needed - just verifying no unhandled exception
