"""Dashboard and analytics routes."""
from datetime import datetime, timezone
from fastapi import APIRouter
from ..database import get_db
from ..models import DashboardStats

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def get_stats():
    async with get_db() as db:
        # Count by status
        cursor = await db.execute(
            "SELECT status, COUNT(*) as count FROM tickets GROUP BY status"
        )
        status_counts = {row["status"]: row["count"] for row in await cursor.fetchall()}

        # Count by priority
        cursor = await db.execute(
            "SELECT priority, COUNT(*) as count FROM tickets GROUP BY priority"
        )
        priority_counts = {row["priority"]: row["count"] for row in await cursor.fetchall()}

        # Count by category
        cursor = await db.execute(
            "SELECT category, COUNT(*) as count FROM tickets GROUP BY category"
        )
        category_counts = {row["category"]: row["count"] for row in await cursor.fetchall()}

        # Average resolution time
        cursor = await db.execute(
            """SELECT AVG(
                   (julianday(resolved_at) - julianday(created_at)) * 24
               ) as avg_hours
               FROM tickets WHERE resolved_at IS NOT NULL"""
        )
        avg_row = await cursor.fetchone()
        avg_hours = avg_row["avg_hours"] if avg_row and avg_row["avg_hours"] else None

        # SLA breached count
        now = datetime.now(timezone.utc).isoformat()
        cursor = await db.execute(
            """SELECT COUNT(*) as count FROM tickets
               WHERE sla_due_at IS NOT NULL
               AND status NOT IN ('resolved', 'closed')
               AND sla_due_at < ?""",
            (now,),
        )
        sla_row = await cursor.fetchone()
        sla_breached_count = sla_row["count"] if sla_row else 0

        # Recent tickets
        cursor = await db.execute(
            """SELECT t.*, c.name as customer_name
               FROM tickets t JOIN customers c ON t.customer_id = c.id
               ORDER BY t.created_at DESC LIMIT 10"""
        )
        recent = [dict(r) for r in await cursor.fetchall()]

        total = sum(status_counts.values())

        return DashboardStats(
            total_tickets=total,
            open_tickets=status_counts.get("open", 0),
            in_progress_tickets=status_counts.get("in_progress", 0),
            resolved_tickets=status_counts.get("resolved", 0),
            closed_tickets=status_counts.get("closed", 0),
            avg_resolution_hours=round(avg_hours, 1) if avg_hours else None,
            tickets_by_priority=priority_counts,
            tickets_by_category=category_counts,
            recent_tickets=recent,
            sla_breached=sla_breached_count,
        )
