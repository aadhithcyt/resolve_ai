"""Real-time customer-agent chat over WebSockets."""
import asyncio
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from typing import Optional
from .database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


class ChatMessage(BaseModel):
    sender: str  # 'customer' or 'agent'
    content: str
    is_ai_generated: bool = False


# In-memory registry of active WebSocket connections per ticket
# ticket_id -> list of (websocket, role, identity)
_chat_connections: dict[int, list[tuple[WebSocket, str, str]]] = {}
_chat_lock = asyncio.Lock()


async def _broadcast(ticket_id: int, message: dict):
    """Send a message to all connections for a ticket."""
    recipients = _chat_connections.get(ticket_id, [])
    disconnected = []
    for ws, role, identity in recipients:
        try:
            await ws.send_text(json.dumps(message))
        except Exception:
            disconnected.append((ws, role, identity))
    if disconnected:
        async with _chat_lock:
            for item in disconnected:
                try:
                    _chat_connections[ticket_id].remove(item)
                except ValueError:
                    pass


async def _send_history(websocket: WebSocket, ticket_id: int):
    """Send message history to a newly connected client."""
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT id, sender, content, is_ai_generated, created_at
               FROM messages WHERE ticket_id = ? AND sender != 'system'
               ORDER BY created_at ASC""",
            (ticket_id,),
        )
        rows = await cursor.fetchall()
        history = [dict(r) for r in rows]
    await websocket.send_text(json.dumps({"type": "history", "messages": history}))


@router.websocket("/ws/chat/{ticket_id}")
async def websocket_chat(websocket: WebSocket, ticket_id: int):
    """WebSocket endpoint for real-time chat on a ticket.

    Query params:
    - role: 'agent' or 'customer'
    - identity: agent name or customer name
    - token: optional JWT for agent authentication

    Message protocol (client -> server):
        {"type": "message", "sender": "customer"|"agent", "content": "..."}
        {"type": "typing", "identity": "..."}   (typing indicator, not persisted)

    Message protocol (server -> client):
        {"type": "history", "messages": [...]}
        {"type": "message", "id":..., "ticket_id":..., "sender":..., "content":..., "is_ai_generated":..., "created_at":...}
        {"type": "typing", "identity": "..."}
        {"type": "presence", "count": N}
    """
    # Parse query params
    role = websocket.query_params.get("role", "customer")
    identity = websocket.query_params.get("identity", "anonymous")

    # Verify ticket exists
    async with get_db() as db:
        ticket = await db.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,))
        if not await ticket.fetchone():
            await websocket.close(code=4000, reason="Ticket not found")
            return

    await websocket.accept()

    async with _chat_lock:
        _chat_connections.setdefault(ticket_id, []).append((websocket, role, identity))

    # Notify participants of updated connection count
    await _broadcast(ticket_id, {
        "type": "presence",
        "count": len(_chat_connections.get(ticket_id, [])),
    })

    # Send history to the new client
    try:
        await _send_history(websocket, ticket_id)
    except Exception:
        pass

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")

            if msg_type == "message":
                sender = data.get("sender", role)
                content = data.get("content", "").strip()
                is_ai_generated = bool(data.get("is_ai_generated", False))
                if not content:
                    continue

                # Persist to messages table
                now = datetime.now(timezone.utc)
                async with get_db() as db:
                    cursor = await db.execute(
                        """INSERT INTO messages (ticket_id, sender, content, is_ai_generated)
                           VALUES (?, ?, ?, ?)""",
                        (ticket_id, sender, content, is_ai_generated),
                    )
                    msg_id = cursor.lastrowid
                    await db.commit()

                payload = {
                    "type": "message",
                    "id": msg_id,
                    "ticket_id": ticket_id,
                    "sender": sender,
                    "content": content,
                    "is_ai_generated": is_ai_generated,
                    "created_at": now.isoformat(),
                }
                await _broadcast(ticket_id, payload)

            elif msg_type == "typing":
                # Relay typing indicator to others (do not broadcast to self)
                others = [
                    (ws, r, i) for ws, r, i in _chat_connections.get(ticket_id, [])
                    if ws is not websocket
                ]
                for ws, _, _ in others:
                    try:
                        await ws.send_text(json.dumps({
                            "type": "typing",
                            "identity": identity,
                        }))
                    except Exception:
                        pass

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket chat error for ticket {ticket_id}: {e}")
    finally:
        async with _chat_lock:
            conns = _chat_connections.get(ticket_id, [])
            if (websocket, role, identity) in conns:
                conns.remove((websocket, role, identity))
            if not conns:
                _chat_connections.pop(ticket_id, None)
        try:
            await _broadcast(ticket_id, {
                "type": "presence",
                "count": len(_chat_connections.get(ticket_id, [])),
            })
        except Exception:
            pass
