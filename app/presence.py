"""Real-time agent presence tracking."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from .database import get_db

router = APIRouter(prefix="/api/presence", tags=["presence"])

# Agents are considered "online" if their heartbeat is within this window
ONLINE_WINDOW_SECONDS = 90


class HeartbeatRequest(BaseModel):
    agent_id: str
    status: Optional[str] = "online"  # online, away, busy


@router.post("/heartbeat")
async def heartbeat(request: HeartbeatRequest):
    """Agent pings this endpoint (every ~30s) to signal it is online."""
    if not request.agent_id or not request.agent_id.strip():
        raise HTTPException(status_code=400, detail="agent_id is required")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ONLINE_WINDOW_SECONDS)

    async with get_db() as db:
        # Upsert presence row
        existing = await db.execute(
            "SELECT agent_id FROM presence WHERE agent_id = ?", (request.agent_id,)
        )
        if await existing.fetchone():
            await db.execute(
                """UPDATE presence
                   SET last_seen = ?, status = ?, expires_at = ?
                   WHERE agent_id = ?""",
                (now.isoformat(), request.status, expires_at.isoformat(), request.agent_id),
            )
        else:
            await db.execute(
                """INSERT INTO presence (agent_id, last_seen, status, expires_at)
                   VALUES (?, ?, ?, ?)""",
                (request.agent_id, now.isoformat(), request.status, expires_at.isoformat()),
            )
        await db.commit()

    return {"ok": True, "agent_id": request.agent_id, "status": request.status}


@router.get("/online")
async def online_agents():
    """Return list of currently online agents (heartbeat within ONLINE_WINDOW_SECONDS)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=ONLINE_WINDOW_SECONDS)).isoformat()

    async with get_db() as db:
        cursor = await db.execute(
            """SELECT agent_id, last_seen, status
               FROM presence
               WHERE last_seen > ? AND status != 'offline'
               ORDER BY last_seen DESC""",
            (cutoff,),
        )
        rows = await cursor.fetchall()
        agents = [dict(r) for r in rows]

    return {"agents": agents, "count": len(agents)}
