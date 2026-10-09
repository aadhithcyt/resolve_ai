"""Customer portal: public API for customers to check their ticket status."""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from .database import get_db

router = APIRouter(prefix="/api/portal", tags=["customer_portal"])


class PortalTicketResponse(BaseModel):
    id: int
    subject: str
    status: str
    priority: str
    category: str
    sentiment: Optional[str] = None
    sla_due_at: Optional[str] = None
    sla_breached: Optional[bool] = None
    created_at: str
    updated_at: str


class PortalMessageResponse(BaseModel):
    id: int
    sender: str
    content: str
    created_at: str


@router.get("/tickets", response_model=List[PortalTicketResponse])
async def get_customer_tickets(email: str = Query(..., description="Customer email")):
    """Get all tickets for a customer by email (public endpoint, no auth)."""
    async with get_db() as db:
        # Find customer by email
        cursor = await db.execute("SELECT id FROM customers WHERE email = ?", (email,))
        customer = await cursor.fetchone()
        if not customer:
            return []

        customer_id = customer["id"]
        cursor = await db.execute(
            "SELECT * FROM tickets WHERE customer_id = ? ORDER BY created_at DESC",
            (customer_id,),
        )
        tickets = [dict(r) for r in await cursor.fetchall()]

        # Compute SLA breach status
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        for t in tickets:
            t["sla_breached"] = False
            if t.get("sla_due_at") and t["status"] not in ("resolved", "closed"):
                try:
                    sla_due = datetime.fromisoformat(t["sla_due_at"].replace("Z", "+00:00"))
                    t["sla_breached"] = now > sla_due
                except (ValueError, TypeError):
                    pass

        return tickets


@router.get("/tickets/{ticket_id}", response_model=PortalTicketResponse)
async def get_customer_ticket(ticket_id: int, email: str = Query(..., description="Customer email")):
    """Get a specific ticket by ID, verifying the customer owns it."""
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT t.* FROM tickets t
               JOIN customers c ON t.customer_id = c.id
               WHERE t.id = ? AND c.email = ?""",
            (ticket_id, email),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Ticket not found")

        ticket = dict(row)
        ticket["sla_breached"] = False
        if ticket.get("sla_due_at") and ticket["status"] not in ("resolved", "closed"):
            try:
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                sla_due = datetime.fromisoformat(ticket["sla_due_at"].replace("Z", "+00:00"))
                ticket["sla_breached"] = now > sla_due
            except (ValueError, TypeError):
                pass

        return ticket


@router.get("/tickets/{ticket_id}/messages", response_model=List[PortalMessageResponse])
async def get_customer_messages(ticket_id: int, email: str = Query(..., description="Customer email")):
    """Get messages for a ticket (only customer and agent messages, no internal notes)."""
    async with get_db() as db:
        # Verify ownership
        cursor = await db.execute(
            """SELECT t.id FROM tickets t
               JOIN customers c ON t.customer_id = c.id
               WHERE t.id = ? AND c.email = ?""",
            (ticket_id, email),
        )
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Ticket not found")

        cursor = await db.execute(
            "SELECT id, sender, content, created_at FROM messages WHERE ticket_id = ? AND sender != 'system' ORDER BY created_at ASC",
            (ticket_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]
