"""SLA reporting: historical trends and compliance metrics."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Query
from typing import Optional
from pydantic import BaseModel
from ..database import get_db

router = APIRouter(prefix="/api/dashboard", tags=["sla_reporting"])


class SLAReport(BaseModel):
    period_start: str
    period_end: str
    total_tickets: int
    resolved_within_sla: int
    resolved_after_sla: int
    still_open_past_sla: int
    sla_compliance_rate: Optional[float]
    avg_resolution_hours: Optional[float]
    tickets_by_priority: dict
    daily_breakdown: list


@router.get("/sla-report", response_model=SLAReport)
async def get_sla_report(days: int = Query(30, ge=1, le=365)):
    """Get SLA compliance report for the given period."""
    async with get_db() as db:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)

        # Total tickets in period
        cursor = await db.execute(
            "SELECT COUNT(*) as count FROM tickets WHERE created_at >= ?",
            (start.isoformat(),),
        )
        row = await cursor.fetchone()
        total = row["count"] if row else 0

        # Resolved within SLA (resolved_at <= sla_due_at)
        cursor = await db.execute(
            """SELECT COUNT(*) as count FROM tickets
               WHERE resolved_at IS NOT NULL
               AND sla_due_at IS NOT NULL
               AND resolved_at <= sla_due_at
               AND created_at >= ?""",
            (start.isoformat(),),
        )
        row = await cursor.fetchone()
        within_sla = row["count"] if row else 0

        # Resolved after SLA (resolved_at > sla_due_at)
        cursor = await db.execute(
            """SELECT COUNT(*) as count FROM tickets
               WHERE resolved_at IS NOT NULL
               AND sla_due_at IS NOT NULL
               AND resolved_at > sla_due_at
               AND created_at >= ?""",
            (start.isoformat(),),
        )
        row = await cursor.fetchone()
        after_sla = row["count"] if row else 0

        # Still open and past SLA
        cursor = await db.execute(
            """SELECT COUNT(*) as count FROM tickets
               WHERE status NOT IN ('resolved', 'closed')
               AND sla_due_at IS NOT NULL
               AND sla_due_at < ?""",
            (now.isoformat(),),
        )
        row = await cursor.fetchone()
        past_sla = row["count"] if row else 0

        # Average resolution time
        cursor = await db.execute(
            """SELECT AVG((julianday(resolved_at) - julianday(created_at)) * 24) as avg_hours
               FROM tickets WHERE resolved_at IS NOT NULL AND created_at >= ?""",
            (start.isoformat(),),
        )
        row = await cursor.fetchone()
        avg_hours = row["avg_hours"] if row and row["avg_hours"] else None

        # Tickets by priority
        cursor = await db.execute(
            """SELECT priority, COUNT(*) as count FROM tickets
               WHERE created_at >= ? GROUP BY priority""",
            (start.isoformat(),),
        )
        by_priority = {r["priority"]: r["count"] for r in await cursor.fetchall()}

        # Daily breakdown
        cursor = await db.execute(
            """SELECT date(created_at) as day, COUNT(*) as count,
                      SUM(CASE WHEN resolved_at IS NOT NULL AND sla_due_at IS NOT NULL AND resolved_at <= sla_due_at THEN 1 ELSE 0 END) as within_sla
               FROM tickets WHERE created_at >= ?
               GROUP BY date(created_at) ORDER BY day""",
            (start.isoformat(),),
        )
        daily = [{"date": r["day"], "total": r["count"], "within_sla": r["within_sla"] or 0} for r in await cursor.fetchall()]

        resolved_total = within_sla + after_sla
        compliance_rate = round(within_sla / resolved_total * 100, 1) if resolved_total > 0 else None

        return SLAReport(
            period_start=start.isoformat(),
            period_end=now.isoformat(),
            total_tickets=total,
            resolved_within_sla=within_sla,
            resolved_after_sla=after_sla,
            still_open_past_sla=past_sla,
            sla_compliance_rate=compliance_rate,
            avg_resolution_hours=round(avg_hours, 1) if avg_hours else None,
            tickets_by_priority=by_priority,
            daily_breakdown=daily,
        )
