"""Team collaboration: internal mentions and @mentions in tickets."""
import re
import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from .database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mentions", tags=["mentions"])


class MentionCreate(BaseModel):
    ticket_id: int
    mentioned_agent_email: str
    note: str = Field(..., min_length=1)
    is_internal: bool = True  # Internal notes not visible to customers


class MentionResponse(BaseModel):
    id: int
    ticket_id: int
    mentioned_agent_email: str
    note: str
    is_internal: bool
    created_at: str
    created_by: Optional[str] = None


@router.post("/", response_model=MentionResponse, status_code=201)
async def create_mention(mention: MentionCreate):
    """Create an @mention in a ticket. Internal notes are not visible to customers."""
    async with get_db() as db:
        # Verify ticket exists
        cursor = await db.execute("SELECT id FROM tickets WHERE id = ?", (mention.ticket_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Ticket not found")

        # Verify mentioned agent exists
        cursor = await db.execute(
            "SELECT email FROM agents WHERE email = ?",
            (mention.mentioned_agent_email,),
        )
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Mentioned agent not found")

        # Insert mention as internal system message
        now = datetime.now(timezone.utc).isoformat()
        content = f"[@{mention.mentioned_agent_email}] {mention.note}"
        cursor = await db.execute(
            """INSERT INTO messages (ticket_id, sender, content, is_ai_generated, created_at)
               VALUES (?, 'system', ?, 0, ?)""",
            (mention.ticket_id, content, now),
        )
        await db.commit()

        return {
            "id": cursor.lastrowid,
            "ticket_id": mention.ticket_id,
            "mentioned_agent_email": mention.mentioned_agent_email,
            "note": mention.note,
            "is_internal": mention.is_internal,
            "created_at": now,
        }


@router.get("/ticket/{ticket_id}", response_model=list[MentionResponse])
async def get_ticket_mentions(ticket_id: int):
    """Get all @mentions for a ticket."""
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT id, ticket_id, content, created_at FROM messages
               WHERE ticket_id = ? AND content LIKE '@%'
               ORDER BY created_at DESC""",
            (ticket_id,),
        )
        mentions = []
        for row in await cursor.fetchall():
            data = dict(row)
            # Extract mentioned email from content
            match = re.match(r"\[@([^\]]+)\]", data["content"])
            if match:
                mentions.append({
                    "id": data["id"],
                    "ticket_id": data["ticket_id"],
                    "mentioned_agent_email": match.group(1),
                    "note": data["content"][match.end():].strip(),
                    "is_internal": True,
                    "created_at": data["created_at"],
                })
        return mentions


@router.get("/agent/{email}", response_model=list[MentionResponse])
async def get_agent_mentions(email: str):
    """Get all @mentions for a specific agent."""
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT id, ticket_id, content, created_at FROM messages
               WHERE content LIKE ?
               ORDER BY created_at DESC""",
            (f"%[@{email}]%",),
        )
        mentions = []
        for row in await cursor.fetchall():
            data = dict(row)
            match = re.match(r"\[@([^\]]+)\]", data["content"])
            if match:
                mentions.append({
                    "id": data["id"],
                    "ticket_id": data["ticket_id"],
                    "mentioned_agent_email": match.group(1),
                    "note": data["content"][match.end():].strip(),
                    "is_internal": True,
                    "created_at": data["created_at"],
                })
        return mentions
