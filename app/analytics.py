"""AI performance analytics: track reply quality, acceptance rates, resolution impact."""
import logging
from datetime import datetime, timezone
from typing import Optional

from .database import get_db

logger = logging.getLogger(__name__)


async def track_ai_reply(
    ticket_id: int,
    reply_text: str,
    tools_used: list,
    tool_calls_made: int,
    reasoning: str,
) -> None:
    """Track an AI-generated reply for analytics."""
    async with get_db() as db:
        await db.execute(
            """INSERT INTO ai_analytics (ticket_id, reply_text, tools_used, tool_calls_made, reasoning, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ticket_id, reply_text, ",".join(tools_used), tool_calls_made, reasoning,
             datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()


async def track_ai_reply_accepted(ticket_id: int, reply_text: str) -> None:
    """Track when an AI reply is accepted/used by an agent."""
    async with get_db() as db:
        await db.execute(
            "UPDATE ai_analytics SET accepted = 1 WHERE ticket_id = ? AND reply_text = ?",
            (ticket_id, reply_text),
        )
        await db.commit()


async def get_ai_analytics() -> dict:
    """Get AI performance metrics."""
    async with get_db() as db:
        # Total AI replies
        cursor = await db.execute("SELECT COUNT(*) as count FROM ai_analytics")
        row = await cursor.fetchone()
        total = row["count"] if row else 0

        # Accepted replies
        cursor = await db.execute("SELECT COUNT(*) as count FROM ai_analytics WHERE accepted = 1")
        row = await cursor.fetchone()
        accepted = row["count"] if row else 0

        # Average tool calls per reply
        cursor = await db.execute("SELECT AVG(tool_calls_made) as avg FROM ai_analytics")
        row = await cursor.fetchone()
        avg_tools = row["avg"] if row and row["avg"] else 0

        # Most used tools
        cursor = await db.execute("SELECT tools_used FROM ai_analytics")
        tool_counts = {}
        for row in await cursor.fetchall():
            for tool in row["tools_used"].split(","):
                if tool:
                    tool_counts[tool] = tool_counts.get(tool, 0) + 1

        # Recent AI activity
        cursor = await db.execute(
            "SELECT * FROM ai_analytics ORDER BY created_at DESC LIMIT 10"
        )
        recent = [dict(r) for r in await cursor.fetchall()]

        return {
            "total_ai_replies": total,
            "accepted_replies": accepted,
            "acceptance_rate": round(accepted / total * 100, 1) if total > 0 else 0,
            "avg_tool_calls": round(avg_tools, 1),
            "tool_usage": tool_counts,
            "recent_activity": recent,
        }
