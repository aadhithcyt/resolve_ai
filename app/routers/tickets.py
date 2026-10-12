"""Ticket management routes with SLA tracking."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from ..database import get_db
from ..models import TicketCreate, TicketUpdate, TicketResponse, MessageCreate, MessageResponse
from ..ai import analyze_sentiment
from ..config import SLA_TARGETS_HOURS, parse_ts
from ..triage import classify_ticket
from ..escalation import check_escalation_rules

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


def _compute_sla_due_at(priority: str, created_at: Optional[datetime] = None) -> datetime:
    """Compute SLA due time based on priority."""
    hours = SLA_TARGETS_HOURS.get(priority, 48)
    base = created_at or datetime.now(timezone.utc)
    return base + timedelta(hours=hours)


def _is_sla_breached(sla_due_at: Optional[datetime], status: str, now: Optional[datetime] = None) -> bool:
    """Check if SLA is breached (ticket still open past due)."""
    if not sla_due_at:
        return False
    if status in ("resolved", "closed"):
        return False
    now = now or datetime.now(timezone.utc)
    return now > sla_due_at


@router.post("/", response_model=TicketResponse, status_code=201)
async def create_ticket(ticket: TicketCreate):
    async with get_db() as db:
        # Verify customer exists
        customer = await db.execute(
            "SELECT id FROM customers WHERE id = ?", (ticket.customer_id,)
        )
        if not await customer.fetchone():
            raise HTTPException(status_code=404, detail="Customer not found")

        # Analyze sentiment
        sentiment_result = await analyze_sentiment(ticket.description)

        # Auto-triage: classify category and priority with AI
        triage_result = await classify_ticket(ticket.subject, ticket.description)
        final_category = triage_result.get("category", ticket.category)
        final_priority = triage_result.get("priority", ticket.priority)

        # Compute SLA
        now = datetime.now(timezone.utc)
        sla_due = _compute_sla_due_at(final_priority, now)

        cursor = await db.execute(
            """INSERT INTO tickets (customer_id, subject, description, priority, category, sentiment, sla_due_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (ticket.customer_id, ticket.subject, ticket.description,
             final_priority, final_category, sentiment_result["sentiment"],
             sla_due.isoformat()),
        )
        ticket_id = cursor.lastrowid

        # Add initial message
        await db.execute(
            "INSERT INTO messages (ticket_id, sender, content) VALUES (?, ?, ?)",
            (ticket_id, "customer", ticket.description),
        )
        await db.commit()

        row = await db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        ticket_data = dict(await row.fetchone())
        ticket_data["sla_breached"] = _is_sla_breached(
            parse_ts(ticket_data["sla_due_at"]),
            ticket_data["status"],
            now,
        )
        return ticket_data


@router.get("/", response_model=List[TicketResponse])
async def list_tickets(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    customer_id: Optional[int] = None,
    search: Optional[str] = None,
    sla_breached: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
):
    async with get_db() as db:
        query = "SELECT * FROM tickets WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if priority:
            query += " AND priority = ?"
            params.append(priority)
        if category:
            query += " AND category = ?"
            params.append(category)
        if customer_id:
            query += " AND customer_id = ?"
            params.append(customer_id)
        if search:
            query += " AND (subject LIKE ? OR description LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, skip])

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        now = datetime.now(timezone.utc)
        results = []
        for r in rows:
            t = dict(r)
            t["sla_breached"] = _is_sla_breached(
                parse_ts(t.get("sla_due_at")),
                t["status"],
                now,
            )
            if sla_breached is not None and t["sla_breached"] != sla_breached:
                continue
            results.append(t)
        return results


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: int):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Ticket not found")
        ticket_data = dict(row)
        ticket_data["sla_breached"] = _is_sla_breached(
            parse_ts(ticket_data.get("sla_due_at")),
            ticket_data["status"],
            datetime.now(timezone.utc),
        )
        return ticket_data


@router.put("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(ticket_id: int, ticket: TicketUpdate):
    async with get_db() as db:
        existing = await db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        existing_row = await existing.fetchone()
        if not existing_row:
            raise HTTPException(status_code=404, detail="Ticket not found")

        existing_data = dict(existing_row)
        fields = []
        values = []
        for field, value in ticket.model_dump(exclude_unset=True).items():
            # Allow explicit None for assigned_to (unassignment); skip other None values
            if value is not None or field == "assigned_to":
                fields.append(f"{field} = ?")
                values.append(value)

        # Recompute SLA if priority changed
        new_priority = ticket.priority or existing_data["priority"]
        if ticket.priority and ticket.priority != existing_data["priority"]:
            now = datetime.now(timezone.utc)
            sla_due = _compute_sla_due_at(new_priority, now)
            fields.append("sla_due_at = ?")
            values.append(sla_due.isoformat())

        # Set resolved_at when status changes to resolved.
        # Use an aware UTC ISO string, not CURRENT_TIMESTAMP: the SLA report
        # compares resolved_at <= sla_due_at as strings, and a naive
        # "YYYY-MM-DD HH:MM:SS" sorts differently from an aware
        # "YYYY-MM-DDTHH:MM:SS+00:00" at the same instant.
        if ticket.status == "resolved":
            fields.append("resolved_at = ?")
            values.append(datetime.now(timezone.utc).isoformat())

        if fields:
            fields.append("updated_at = ?")
            values.append(datetime.now(timezone.utc).isoformat())
            values.append(ticket_id)
            await db.execute(
                f"UPDATE tickets SET {', '.join(fields)} WHERE id = ?", values
            )
            await db.commit()

        cursor = await db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        ticket_data = dict(await cursor.fetchone())
        ticket_data["sla_breached"] = _is_sla_breached(
            parse_ts(ticket_data.get("sla_due_at")),
            ticket_data["status"],
            datetime.now(timezone.utc),
        )
        return ticket_data


@router.delete("/{ticket_id}", status_code=204)
async def delete_ticket(ticket_id: int):
    async with get_db() as db:
        cursor = await db.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Ticket not found")


@router.get("/{ticket_id}/messages", response_model=List[MessageResponse])
async def get_messages(ticket_id: int):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM messages WHERE ticket_id = ? ORDER BY created_at ASC",
            (ticket_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


@router.post("/{ticket_id}/messages", response_model=MessageResponse, status_code=201)
async def add_message(ticket_id: int, message: MessageCreate):
    async with get_db() as db:
        ticket = await db.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,))
        if not await ticket.fetchone():
            raise HTTPException(status_code=404, detail="Ticket not found")

        cursor = await db.execute(
            "INSERT INTO messages (ticket_id, sender, content, is_ai_generated) VALUES (?, ?, ?, ?)",
            (ticket_id, message.sender, message.content, message.is_ai_generated),
        )
        await db.commit()

        row = await db.execute("SELECT * FROM messages WHERE id = ?", (cursor.lastrowid,))
        return dict(await row.fetchone())


@router.get("/{ticket_id}/sla")
async def get_ticket_sla(ticket_id: int):
    """Get SLA details for a ticket."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT sla_due_at, sla_breached, status, priority, created_at FROM tickets WHERE id = ?",
            (ticket_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Ticket not found")

        data = dict(row)
        sla_due = parse_ts(data.get("sla_due_at"))
        now = datetime.now(timezone.utc)
        breached = _is_sla_breached(sla_due, data["status"], now)
        hours_remaining = None
        if sla_due and data["status"] not in ("resolved", "closed"):
            hours_remaining = round((sla_due - now).total_seconds() / 3600, 1)

        return {
            "sla_due_at": data["sla_due_at"],
            "sla_breached": breached,
            "status": data["status"],
            "priority": data["priority"],
            "hours_remaining": hours_remaining,
        }
