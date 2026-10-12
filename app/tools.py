"""Tool definitions and executor for the AI agent."""
from typing import Any
import logging

logger = logging.getLogger(__name__)


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_ticket_info",
            "description": "Get detailed information about a support ticket including status, priority, and SLA",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ticket ID to look up"
                    }
                },
                "required": ["ticket_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_info",
            "description": "Get customer details including contact info and ticket history",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "integer",
                        "description": "The customer ID to look up"
                    }
                },
                "required": ["customer_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "Search the knowledge base for relevant articles, FAQs, and solutions. Use this to find answers to common support questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for the knowledge base"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_ticket",
            "description": "Escalate a ticket to a higher priority. Use when the customer is very upset, the issue is critical, or SLA is at risk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ticket ID to escalate"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for escalation"
                    },
                    "new_priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "urgent"],
                        "description": "New priority level"
                    }
                },
                "required": ["ticket_id", "reason", "new_priority"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_ticket_note",
            "description": "Add an internal note to a ticket. Use to record internal observations or decisions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ticket ID to add note to"
                    },
                    "note": {
                        "type": "string",
                        "description": "The internal note content"
                    }
                },
                "required": ["ticket_id", "note"]
            }
        }
    }
]


async def get_ticket_info(ticket_id: int) -> dict:
    """Get ticket details from the database."""
    from .database import get_db
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = await cursor.fetchone()
        if not row:
            return {"error": f"Ticket {ticket_id} not found"}
        result = dict(row)

        # Include attachments
        cursor2 = await db.execute(
            "SELECT id, filename, content_type, uploaded_at FROM attachments WHERE ticket_id = ? ORDER BY uploaded_at DESC",
            (ticket_id,),
        )
        result["attachments"] = [dict(r) for r in await cursor2.fetchall()]
        return result


async def get_customer_info(customer_id: int) -> dict:
    """Get customer details, ticket history, and conversation summaries."""
    from .database import get_db
    from .memory import get_conversation_context
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
        customer = await cursor.fetchone()
        if not customer:
            return {"error": f"Customer {customer_id} not found"}

        # Get ticket history
        cursor2 = await db.execute(
            "SELECT id, subject, status, priority, created_at FROM tickets WHERE customer_id = ? ORDER BY created_at DESC LIMIT 5",
            (customer_id,)
        )
        tickets = [dict(r) for r in await cursor2.fetchall()]

        # Get conversation context (last 5 tickets with messages)
        conversation_context = await get_conversation_context(customer_id)

        # Build conversation summaries
        conversation_summaries = []
        for ticket in conversation_context:
            summary = {
                "ticket_id": ticket["id"],
                "subject": ticket["subject"],
                "status": ticket["status"],
                "priority": ticket["priority"],
                "message_count": len(ticket.get("messages", [])),
                "last_message": None,
            }
            if ticket.get("messages"):
                last_msg = ticket["messages"][-1]
                summary["last_message"] = {
                    "sender": last_msg["sender"],
                    "content": last_msg["content"][:200],
                    "is_ai_generated": last_msg["is_ai_generated"],
                }
            conversation_summaries.append(summary)

        result = dict(customer)
        result["recent_tickets"] = tickets
        result["conversation_summaries"] = conversation_summaries
        return result


async def search_knowledge_base(query: str) -> dict:
    """Search the knowledge base for relevant articles."""
    from .database import get_db
    async with get_db() as db:
        # Use FTS5 if available, fallback to LIKE
        try:
            cursor = await db.execute(
                "SELECT title, content FROM knowledge_base WHERE content MATCH ? OR title MATCH ? LIMIT 5",
                (query, query)
            )
        except Exception:
            # Fallback to LIKE search
            cursor = await db.execute(
                "SELECT title, content FROM knowledge_base WHERE content LIKE ? OR title LIKE ? LIMIT 5",
                (f"%{query}%", f"%{query}%")
            )
        rows = await cursor.fetchall()
        if not rows:
            return {"results": [], "message": "No matching articles found"}
        return {"results": [dict(r) for r in rows], "query": query}


async def escalate_ticket(ticket_id: int, reason: str, new_priority: str) -> dict:
    """Escalate a ticket to a higher priority."""
    from .database import get_db
    from .routers.tickets import _compute_sla_due_at
    from datetime import datetime, timezone

    async with get_db() as db:
        cursor = await db.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,))
        if not await cursor.fetchone():
            return {"error": f"Ticket {ticket_id} not found"}

        now = datetime.now(timezone.utc)
        sla_due = _compute_sla_due_at(new_priority, now)

        await db.execute(
            "UPDATE tickets SET priority = ?, sla_due_at = ?, updated_at = ? WHERE id = ?",
            (new_priority, sla_due.isoformat(), now.isoformat(), ticket_id)
        )
        await db.commit()

        return {
            "ticket_id": ticket_id,
            "new_priority": new_priority,
            "reason": reason,
            "sla_due_at": sla_due.isoformat(),
            "status": "escalated"
        }


async def add_ticket_note(ticket_id: int, note: str) -> dict:
    """Add an internal note as a system message."""
    from .database import get_db

    async with get_db() as db:
        cursor = await db.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,))
        if not await cursor.fetchone():
            return {"error": f"Ticket {ticket_id} not found"}

        await db.execute(
            "INSERT INTO messages (ticket_id, sender, content, is_ai_generated) VALUES (?, ?, ?, ?)",
            (ticket_id, "system", f"[AI Agent Note] {note}", True)
        )
        await db.commit()

        return {"ticket_id": ticket_id, "note": note, "status": "added"}


class ToolExecutor:
    """Dispatches tool calls to the correct function."""

    def __init__(self):
        self.tools = {
            "get_ticket_info": get_ticket_info,
            "get_customer_info": get_customer_info,
            "search_knowledge_base": search_knowledge_base,
            "escalate_ticket": escalate_ticket,
            "add_ticket_note": add_ticket_note,
        }

    async def execute(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool by name with given arguments."""
        if tool_name not in self.tools:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            func = self.tools[tool_name]
            return await func(**arguments)
        except Exception as e:
            logger.error(f"Tool execution error for {tool_name}: {e}")
            return {"error": str(e)}

    def get_tool_names(self) -> list:
        """Get list of available tool names."""
        return list(self.tools.keys())
