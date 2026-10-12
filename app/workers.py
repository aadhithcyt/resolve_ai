"""Background workers for ResolveAI: SLA breach scanning and email receiving."""
import asyncio
import email
import imaplib
import logging
from datetime import datetime, timezone
from typing import Optional

import aiosqlite

from .config import (
    DB_PATH,
    EMAIL_HOST,
    EMAIL_PORT,
    EMAIL_USER,
    EMAIL_PASSWORD,
    EMAIL_FROM,
    EMAIL_TO,
    parse_ts,
)
from .database import get_db
from .email import notify_sla_breach, send_email

logger = logging.getLogger(__name__)

# ─── SLA Breach Scanner ──────────────────────────────────────────────────────

SLA_SCAN_INTERVAL = 300  # 5 minutes


async def _find_sla_breached_tickets() -> list[dict]:
    """Find tickets that are past SLA due date and still open."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT t.id, t.subject, t.description, t.status, t.priority,
                      t.sla_due_at, t.sla_breached, t.customer_id,
                      c.name as customer_name, c.email as customer_email
               FROM tickets t
               JOIN customers c ON t.customer_id = c.id
               WHERE t.sla_due_at IS NOT NULL
                 AND t.status NOT IN ('resolved', 'closed')
                 AND t.sla_due_at < ?
                 AND t.sla_breached = 0""",
            (now,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def _mark_sla_breached(ticket_id: int) -> None:
    """Mark a ticket as SLA breached."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tickets SET sla_breached = 1, updated_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), ticket_id),
        )
        await db.commit()


async def _send_sla_breach_notification(ticket: dict) -> bool:
    """Send SLA breach notification email."""
    # parse_ts handles both naive SQLite timestamps and aware ISO strings.
    # Previously this raised TypeError on the Windows path (where SQLite writes
    # naive values), which killed the whole scanner iteration before the ticket
    # could be marked breached.
    sla_due = parse_ts(ticket["sla_due_at"])
    if sla_due is None:
        return False
    now = datetime.now(timezone.utc)
    hours_overdue = (now - sla_due).total_seconds() / 3600

    return await notify_sla_breach(
        ticket_id=ticket["id"],
        subject=ticket["subject"],
        customer_name=ticket["customer_name"],
        priority=ticket["priority"],
        hours_overdue=hours_overdue,
    )


async def sla_breach_scanner(stop_event: Optional[asyncio.Event] = None) -> None:
    """Background task that scans for SLA breaches every 5 minutes.

    Queries tickets past SLA due date that are still open, marks them as
    breached, and sends email notifications.
    """
    logger.info("SLA breach scanner started")

    while True:
        try:
            breached_tickets = await _find_sla_breached_tickets()
            if breached_tickets:
                logger.info(f"Found {len(breached_tickets)} SLA breached ticket(s)")
                for ticket in breached_tickets:
                    await _mark_sla_breached(ticket["id"])
                    await _send_sla_breach_notification(ticket)
                    logger.info(f"Marked ticket #{ticket['id']} as SLA breached")
            else:
                logger.debug("No SLA breaches found")
        except Exception as e:
            logger.error(f"Error in SLA breach scanner: {e}")

        # Wait for interval or until stopped
        if stop_event is not None:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=SLA_SCAN_INTERVAL)
                break  # stop_event was set
            except asyncio.TimeoutError:
                pass  # Normal interval timeout, continue loop
        else:
            await asyncio.sleep(SLA_SCAN_INTERVAL)

    logger.info("SLA breach scanner stopped")


# ─── Email Receiver ───────────────────────────────────────────────────────────

EMAIL_POLL_INTERVAL = 60  # 60 seconds


async def _fetch_unseen_emails() -> list[dict]:
    """Fetch unseen emails from IMAP inbox."""
    if not EMAIL_HOST or not EMAIL_USER:
        logger.debug("IMAP not configured, skipping email fetch")
        return []

    emails = []
    try:
        # Run blocking IMAP operations in a thread pool.
        # asyncio.get_running_loop() is the correct call inside a coroutine;
        # get_event_loop() is deprecated (Python 3.12+) and raises when no loop
        # is running, which would break this worker.
        loop = asyncio.get_running_loop()
        emails = await loop.run_in_executor(None, _imap_fetch_unseen)
    except Exception as e:
        logger.error(f"Error fetching emails from IMAP: {e}")

    return emails


def _imap_fetch_unseen() -> list[dict]:
    """Blocking IMAP fetch operation (runs in thread pool)."""
    results = []
    mail = None
    try:
        mail = imaplib.IMAP4_SSL(EMAIL_HOST, EMAIL_PORT)
        mail.login(EMAIL_USER, EMAIL_PASSWORD)
        mail.select("inbox")

        status, messages = mail.search(None, "UNSEEN")
        if status != "OK":
            return results

        for num in messages[0].split():
            status, msg_data = mail.fetch(num, "(RFC822)")
            if status != "OK":
                continue

            raw_email = msg_data[0][1]
            parsed = email.message_from_bytes(raw_email)

            # Extract body
            body = ""
            if parsed.is_multipart():
                for part in parsed.walk():
                    if part.get_content_type() == "text/plain":
                        try:
                            body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                            break
                        except Exception:
                            continue
            else:
                try:
                    body = parsed.get_payload(decode=True).decode("utf-8", errors="replace")
                except Exception:
                    body = str(parsed.get_payload())

            # Extract sender email
            from_header = parsed.get("From", "")
            sender_email = ""
            if "<" in from_header and ">" in from_header:
                sender_email = from_header.split("<")[1].split(">")[0]
            elif "@" in from_header:
                sender_email = from_header.strip()

            results.append({
                "message_id": parsed.get("Message-ID", ""),
                "subject": parsed.get("Subject", ""),
                "from": sender_email,
                "from_header": from_header,
                "body": body.strip(),
                "date": parsed.get("Date", ""),
            })

        mail.logout()
    except Exception as e:
        logger.error(f"IMAP error: {e}")
        if mail:
            try:
                mail.logout()
            except Exception:
                pass

    return results


async def _find_customer_by_email(email_addr: str) -> Optional[dict]:
    """Find a customer by email address."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM customers WHERE email = ?",
            (email_addr,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def _create_ticket_from_email(email_data: dict) -> Optional[dict]:
    """Create a ticket from an incoming email."""
    sender_email = email_data.get("from", "")
    if not sender_email:
        logger.warning("Email has no sender, skipping")
        return None

    # Find or create customer
    customer = await _find_customer_by_email(sender_email)
    if customer:
        customer_id = customer["id"]
        customer_name = customer["name"]
    else:
        # Create new customer from email
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "INSERT INTO customers (name, email) VALUES (?, ?)",
                (email_data.get("from_header", sender_email), sender_email),
            )
            await db.commit()
            customer_id = cursor.lastrowid
            customer_name = email_data.get("from_header", sender_email)

    # Create ticket
    subject = email_data.get("subject", "Email from customer")
    if not subject:
        subject = "Email from customer"

    body = email_data.get("body", "")
    if not body:
        body = "(empty email body)"

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Write an explicit aware UTC timestamp and a real SLA deadline instead
        # of relying on SQLite's CURRENT_TIMESTAMP. That keeps email-created
        # tickets consistent with API-created ones (which compute sla_due_at
        # from priority) and avoids naive-vs-aware datetime bugs downstream.
        from .routers.tickets import _compute_sla_due_at

        now = datetime.now(timezone.utc)
        sla_due = _compute_sla_due_at("medium", now)
        cursor = await db.execute(
            """INSERT INTO tickets
               (customer_id, subject, description, priority, category, created_at, updated_at, sla_due_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (customer_id, subject, body, "medium", "email",
             now.isoformat(), now.isoformat(), sla_due.isoformat()),
        )
        ticket_id = cursor.lastrowid

        # Add initial message
        await db.execute(
            "INSERT INTO messages (ticket_id, sender, content) VALUES (?, ?, ?)",
            (ticket_id, "customer", body),
        )
        await db.commit()

        # Fetch the created ticket
        row = await db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        ticket = dict(await row.fetchone())

    logger.info(f"Created ticket #{ticket_id} from email by {sender_email}")

    # Send notification
    await send_email(
        subject=f"[ResolveAI] New Ticket #{ticket_id}: {subject}",
        body=f"New support ticket #{ticket_id} has been created from email.\n\nCustomer: {customer_name}\nSubject: {subject}\nPriority: medium\nCategory: email",
    )

    return ticket


async def email_receiver(stop_event: Optional[asyncio.Event] = None) -> None:
    """Background task that polls IMAP inbox every 60 seconds.

    Parses incoming emails and creates tickets from them.
    """
    logger.info("Email receiver started")

    while True:
        try:
            emails = await _fetch_unseen_emails()
            if emails:
                logger.info(f"Received {len(emails)} new email(s)")
                for email_data in emails:
                    try:
                        await _create_ticket_from_email(email_data)
                    except Exception as e:
                        logger.error(f"Error creating ticket from email: {e}")
            else:
                logger.debug("No new emails")
        except Exception as e:
            logger.error(f"Error in email receiver: {e}")

        # Wait for interval or until stopped
        if stop_event is not None:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=EMAIL_POLL_INTERVAL)
                break  # stop_event was set
            except asyncio.TimeoutError:
                pass  # Normal interval timeout, continue loop
        else:
            await asyncio.sleep(EMAIL_POLL_INTERVAL)

    logger.info("Email receiver stopped")


# ─── Worker Management ────────────────────────────────────────────────────────

_worker_tasks: list[asyncio.Task] = []


async def start_workers() -> list[asyncio.Task]:
    """Start all background workers. Returns the list of tasks."""
    global _worker_tasks
    stop_event = asyncio.Event()

    sla_task = asyncio.create_task(sla_breach_scanner(stop_event))
    email_task = asyncio.create_task(email_receiver(stop_event))

    _worker_tasks = [sla_task, email_task]
    logger.info(f"Started {len(_worker_tasks)} background workers")
    return _worker_tasks


async def stop_workers() -> None:
    """Stop all background workers gracefully."""
    global _worker_tasks
    for task in _worker_tasks:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    _worker_tasks.clear()
    logger.info("All background workers stopped")
