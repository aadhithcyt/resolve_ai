"""Conversation memory for the AI agent.

The agent stores and retrieves contextual information about past
interactions with customers, enabling continuity across tickets.
"""
import logging
from typing import Optional

from .database import get_db

logger = logging.getLogger(__name__)


async def save_memory(
    ticket_id: Optional[int],
    customer_id: int,
    key: str,
    value: str,
) -> dict:
    """Save an agent memory entry.

    Each memory entry is a key-value pair associated with a customer
    and optionally a specific ticket. Duplicate keys are allowed
    (they represent an evolving history); retrieval returns the most
    recent value.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "INSERT INTO agent_memory (ticket_id, customer_id, key, value) "
            "VALUES (?, ?, ?, ?)",
            (ticket_id, customer_id, key, value),
        )
        await db.commit()
        return {
            "id": cursor.lastrowid,
            "ticket_id": ticket_id,
            "customer_id": customer_id,
            "key": key,
            "value": value,
        }


async def get_memory(customer_id: int, key: str) -> Optional[str]:
    """Get the most recent memory value for a customer and key.

    Returns None if no matching memory entry exists.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT value FROM agent_memory "
            "WHERE customer_id = ? AND key = ? "
            "ORDER BY id DESC LIMIT 1",
            (customer_id, key),
        )
        row = await cursor.fetchone()
        return row["value"] if row else None


async def get_conversation_context(customer_id: int) -> list:
    """Return the last 5 tickets (with their messages) for a customer.

    The tickets are ordered most-recent first. Each ticket dict
    includes a ``messages`` list with all associated messages
    ordered chronologically.
    """
    async with get_db() as db:
        # Get last 5 tickets for this customer
        cursor = await db.execute(
            "SELECT id, subject, status, priority, category, ai_reply, "
            "created_at FROM tickets "
            "WHERE customer_id = ? "
            "ORDER BY created_at DESC, id DESC LIMIT 5",
            (customer_id,),
        )
        tickets = [dict(r) for r in await cursor.fetchall()]

        # Get messages for each ticket
        context = []
        for ticket in tickets:
            cursor2 = await db.execute(
                "SELECT sender, content, is_ai_generated, created_at "
                "FROM messages WHERE ticket_id = ? "
                "ORDER BY created_at ASC",
                (ticket["id"],),
            )
            messages = [dict(r) for r in await cursor2.fetchall()]
            ticket["messages"] = messages
            context.append(ticket)

        return context
