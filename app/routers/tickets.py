"""Ticket management routes."""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from ..database import get_db
from ..models import TicketCreate, TicketUpdate, TicketResponse, MessageCreate, MessageResponse
from ..ai import analyze_sentiment

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


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

        cursor = await db.execute(
            """INSERT INTO tickets (customer_id, subject, description, priority, category, sentiment)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ticket.customer_id, ticket.subject, ticket.description,
             ticket.priority, ticket.category, sentiment_result["sentiment"]),
        )
        ticket_id = cursor.lastrowid

        # Add initial message
        await db.execute(
            "INSERT INTO messages (ticket_id, sender, content) VALUES (?, ?, ?)",
            (ticket_id, "customer", ticket.description),
        )
        await db.commit()

        row = await db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        return dict(await row.fetchone())


@router.get("/", response_model=List[TicketResponse])
async def list_tickets(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    customer_id: Optional[int] = None,
    search: Optional[str] = None,
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
        return [dict(r) for r in rows]


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: int):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return dict(row)


@router.put("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(ticket_id: int, ticket: TicketUpdate):
    async with get_db() as db:
        existing = await db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if not await existing.fetchone():
            raise HTTPException(status_code=404, detail="Ticket not found")

        fields = []
        values = []
        for field, value in ticket.model_dump(exclude_unset=True).items():
            if value is not None:
                fields.append(f"{field} = ?")
                values.append(value)

        # Set resolved_at when status changes to resolved
        if ticket.status == "resolved":
            fields.append("resolved_at = CURRENT_TIMESTAMP")

        if fields:
            fields.append("updated_at = CURRENT_TIMESTAMP")
            values.append(ticket_id)
            await db.execute(
                f"UPDATE tickets SET {', '.join(fields)} WHERE id = ?", values
            )
            await db.commit()

        cursor = await db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        return dict(await cursor.fetchone())


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
