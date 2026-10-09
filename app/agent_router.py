"""Agent router for AI-powered support with tool calling."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from .database import get_db
from .agent import run_agent

router = APIRouter(prefix="/api/ai", tags=["agent"])


class AgentRequest(BaseModel):
    ticket_id: int
    tone: Optional[str] = "professional"


class AgentResponse(BaseModel):
    reply: str
    tool_calls_made: int
    tools_used: list
    reasoning: str


@router.post("/agent", response_model=AgentResponse)
async def run_agent_endpoint(request: AgentRequest):
    """Run the AI agent loop for a ticket.

    The agent will:
    1. Gather ticket and customer info
    2. Search the knowledge base
    3. Draft a reply (or escalate if needed)
    """
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

    result = await run_agent(
        ticket_id=request.ticket_id,
        subject=ticket_data["subject"],
        description=ticket_data["description"],
        customer_name=ticket_data["customer_name"],
        category=ticket_data["category"],
    )

    # Store the AI reply on the ticket
    async with get_db() as db:
        await db.execute(
            "UPDATE tickets SET ai_reply = ? WHERE id = ?",
            (result["reply"], request.ticket_id),
        )
        await db.commit()

    return AgentResponse(**result)
