"""SSE streaming for real-time ticket updates."""
import asyncio
import json
import logging
from typing import AsyncGenerator
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from .database import get_db

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
