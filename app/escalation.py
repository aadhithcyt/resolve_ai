"""Escalation engine: automatic ticket routing and escalation rules."""
import logging
from datetime import datetime, timezone
from typing import Optional

from .database import get_db
from .config import SLA_TARGETS_HOURS, parse_ts

logger = logging.getLogger(__name__)


async def check_escalation_rules(ticket_id: int) -> Optional[dict]:
    """Check if a ticket matches any escalation rules.

    Rules:
    1. SLA breached + high priority -> escalate to urgent
    2. Customer has 3+ open tickets -> escalate priority
    3. Ticket open > 48h with no response -> escalate
    4. Negative sentiment + high priority -> escalate

    Returns escalation action dict or None.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT t.*, c.name as customer_name,
                      (SELECT COUNT(*) FROM tickets WHERE customer_id = t.customer_id AND status IN ('open', 'in_progress')) as open_count,
                      (SELECT COUNT(*) FROM messages WHERE ticket_id = t.id AND sender = 'agent') as agent_replies
               FROM tickets t JOIN customers c ON t.customer_id = c.id
               WHERE t.id = ?""",
            (ticket_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        ticket = dict(row)
        now = datetime.now(timezone.utc)

        # Rule 1: SLA breached + high priority -> urgent
        if ticket.get("sla_breached") and ticket["priority"] == "high":
            return await _escalate(ticket_id, "urgent", "SLA breached on high priority ticket")

        # Rule 2: Customer has 3+ open tickets -> escalate
        if ticket.get("open_count", 0) >= 3 and ticket["priority"] != "urgent":
            new_priority = "urgent" if ticket["priority"] == "high" else "high"
            return await _escalate(ticket_id, new_priority, f"Customer has {ticket['open_count']} open tickets")

        # Rule 3: No agent response in 48h
        if ticket.get("agent_replies", 0) == 0 and ticket["status"] == "open":
            # parse_ts normalises both SQLite's naive "YYYY-MM-DD HH:MM:SS" and
            # the app's aware ISO strings to UTC, so the subtraction below can
            # never raise. (It previously did, and the TypeError was swallowed
            # by the except clause, leaving this rule permanently dead.)
            created_dt = parse_ts(ticket.get("created_at"))
            if created_dt is not None:
                hours_open = (now - created_dt).total_seconds() / 3600
                if hours_open > 48 and ticket["priority"] in ("low", "medium"):
                    return await _escalate(ticket_id, "high", f"No agent response for {hours_open:.0f} hours")

        # Rule 4: Negative sentiment + high priority
        if ticket.get("sentiment") == "negative" and ticket["priority"] in ("high", "urgent"):
            return await _escalate(ticket_id, "urgent", "Negative sentiment on high priority ticket")

        return None


async def _escalate(ticket_id: int, new_priority: str, reason: str) -> dict:
    """Perform the escalation."""
    from .routers.tickets import _compute_sla_due_at

    async with get_db() as db:
        now = datetime.now(timezone.utc)
        sla_due = _compute_sla_due_at(new_priority, now)

        await db.execute(
            "UPDATE tickets SET priority = ?, sla_due_at = ?, updated_at = ? WHERE id = ?",
            (new_priority, sla_due.isoformat(), now.isoformat(), ticket_id),
        )
        await db.execute(
            "INSERT INTO messages (ticket_id, sender, content, is_ai_generated) VALUES (?, ?, ?, ?)",
            (ticket_id, "system", f"[Auto-Escalation] Priority changed to {new_priority}. Reason: {reason}", True),
        )
        await db.commit()

        logger.info(f"Ticket {ticket_id} escalated to {new_priority}: {reason}")

        return {
            "ticket_id": ticket_id,
            "new_priority": new_priority,
            "reason": reason,
            "escalated_at": now.isoformat(),
        }
