"""SSE streaming for real-time ticket updates."""
import asyncio
import json
import logging
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from .database import get_db
from .agent import run_agent_streaming

logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])


@router.get("/api/events/tickets")
async def ticket_events():
    """SSE endpoint for real-time ticket updates.

    Clients connect here and receive events when tickets are created/updated.
    Events: ticket_created, ticket_updated, ticket_resolved, sla_breached
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        last_check = 0
        while True:
            try:
                async with get_db() as db:
                    # Check for recently updated tickets
                    cursor = await db.execute(
                        """SELECT id, subject, status, priority, sla_breached, updated_at
                           FROM tickets WHERE updated_at > datetime('now', '-10 seconds')
                           ORDER BY updated_at DESC LIMIT 5"""
                    )
                    rows = await cursor.fetchall()

                    for row in rows:
                        data = dict(row)
                        event_type = "ticket_updated"
                        if data["status"] == "resolved":
                            event_type = "ticket_resolved"
                        if data.get("sla_breached"):
                            event_type = "sla_breached"

                        yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

                        # Also create notification for SLA breaches and new tickets
                        if event_type in ("sla_breached", "ticket_created"):
                            notif_title = "SLA Breached" if event_type == "sla_breached" else "New Ticket"
                            notif_body = f"Ticket #{data['id']}: {data['subject'][:60]}"
                            notif_type = "sla" if event_type == "sla_breached" else "ticket"
                            await db.execute(
                                "INSERT INTO notifications (title, body, type, ticket_id) VALUES (?, ?, ?, ?)",
                                (notif_title, notif_body, notif_type, data["id"]),
                            )
                            await db.commit()
                            notif_data = json.dumps({
                                "title": notif_title,
                                "body": notif_body,
                                "type": notif_type,
                                "ticket_id": data["id"],
                            })
                            yield f"event: notification\ndata: {notif_data}\n\n"

                # Heartbeat every 30 seconds
                yield f": heartbeat\n\n"

                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"SSE error: {e}")
                await asyncio.sleep(10)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class AgentStreamRequest(BaseModel):
    ticket_id: int


@router.post("/api/ai/agent/stream")
async def agent_stream(request: AgentStreamRequest):
    """SSE endpoint for streaming AI agent output.

    Accepts a ticket_id and returns a stream of events:
    - tool_call: when the agent decides to call a tool
    - tool_result: when a tool returns a result
    - reply_chunk: chunks of the final reply text
    - done: when the agent completes
    - error: when an error occurs
    """
    # Fetch ticket info
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

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for event in run_agent_streaming(
                ticket_id=request.ticket_id,
                subject=ticket_data["subject"],
                description=ticket_data["description"],
                customer_name=ticket_data["customer_name"],
                category=ticket_data["category"],
            ):
                event_type = event["type"]
                data = json.dumps(event["data"])
                yield f"event: {event_type}\ndata: {data}\n\n"
        except Exception as e:
            logger.error(f"Agent stream error: {e}")
            error_data = json.dumps({"error": str(e)})
            yield f"event: error\ndata: {error_data}\n\n"
            done_data = json.dumps({
                "reply": f"[AI agent failed: {str(e)}]",
                "tool_calls_made": 0,
                "tools_used": [],
                "reasoning": f"Error: {str(e)}",
            })
            yield f"event: done\ndata: {done_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
