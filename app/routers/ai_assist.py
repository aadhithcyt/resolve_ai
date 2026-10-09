"""AI assistance routes for auto-replies and sentiment."""
from fastapi import APIRouter, HTTPException
from ..database import get_db
from ..models import AIReplyRequest, AIReplyResponse
from ..ai import generate_reply, analyze_sentiment

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/reply", response_model=AIReplyResponse)
async def generate_ai_reply(request: AIReplyRequest):
    """Generate an AI-powered reply draft for a ticket."""
    async with get_db() as db:
        ticket = await db.execute(
            """SELECT t.*, c.name as customer_name
               FROM tickets t JOIN customers c ON t.customer_id = c.id
               WHERE t.id = ?""",
            (request.ticket_id,),
        )
        row = await ticket.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Ticket not found")

        ticket_data = dict(row)

        reply = await generate_reply(
            subject=ticket_data["subject"],
            description=ticket_data["description"],
            customer_name=ticket_data["customer_name"],
            tone=request.tone,
            category=ticket_data["category"],
        )

        # Analyze sentiment of original message
        sentiment_result = await analyze_sentiment(ticket_data["description"])

        # Store the AI reply on the ticket
        await db.execute(
            "UPDATE tickets SET ai_reply = ? WHERE id = ?",
            (reply, request.ticket_id),
        )
        await db.commit()

        return AIReplyResponse(
            reply=reply,
            sentiment=sentiment_result["sentiment"],
            confidence=sentiment_result["confidence"],
        )


@router.post("/sentiment/{ticket_id}")
async def analyze_ticket_sentiment(ticket_id: int):
    """Re-analyze sentiment for a ticket's description."""
    async with get_db() as db:
        ticket = await db.execute(
            "SELECT description FROM tickets WHERE id = ?", (ticket_id,)
        )
        row = await ticket.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Ticket not found")

        result = await analyze_sentiment(row["description"])

        # Update ticket sentiment
        await db.execute(
            "UPDATE tickets SET sentiment = ? WHERE id = ?",
            (result["sentiment"], ticket_id),
        )
        await db.commit()

        return result
