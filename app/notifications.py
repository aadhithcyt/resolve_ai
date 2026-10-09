"""Push notification endpoints for ResolveAI.

Lightweight approach: stores browser push subscriptions in SQLite.
Actual push delivery uses the Service Worker + Web Push API.
For immediate notification delivery, we use SSE (Server-Sent Events)
which the frontend listens to for the notification bell dropdown.
"""
import json
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from .database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class PushSubscription(BaseModel):
    endpoint: str = Field(..., min_length=10, max_length=500)
    keys: dict = Field(..., description="Contains p256dh and auth keys")


class SubscribeResponse(BaseModel):
    status: str
    message: str


class NotificationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=500)
    type: str = Field(default="info", max_length=20)
    ticket_id: Optional[int] = None


@router.post("/subscribe", response_model=SubscribeResponse)
async def subscribe(subscription: PushSubscription):
    """Store a browser push subscription.

    The subscription object contains:
    - endpoint: the push service endpoint URL
    - keys: {p256dh, auth} for encryption
    """
    async with get_db() as db:
        # Upsert subscription by endpoint
        await db.execute(
            """INSERT INTO push_subscriptions (endpoint, p256dh, auth)
               VALUES (?, ?, ?)
               ON CONFLICT(endpoint) DO UPDATE SET p256dh=excluded.p256dh, auth=excluded.auth""",
            (
                subscription.endpoint,
                subscription.keys.get("p256dh", ""),
                subscription.keys.get("auth", ""),
            ),
        )
        await db.commit()
    return SubscribeResponse(status="subscribed", message="Push subscription saved")


@router.post("/send-test", response_model=SubscribeResponse)
async def send_test_notification():
    """Send a test notification to all subscribed clients.

    Creates a notification record that will be delivered via SSE
    to all connected clients and shown in the notification bell.
    """
    async with get_db() as db:
        await db.execute(
            """INSERT INTO notifications (title, body, type)
               VALUES (?, ?, ?)""",
            ("Test Notification", "Push notifications are working! 🎉", "info"),
        )
        await db.commit()
    return SubscribeResponse(status="sent", message="Test notification sent")


@router.get("/")
async def get_notifications(unread_only: bool = False, limit: int = 20):
    """Get recent notifications for the bell dropdown."""
    async with get_db() as db:
        query = "SELECT * FROM notifications"
        if unread_only:
            query += " WHERE read = 0"
        query += " ORDER BY created_at DESC LIMIT ?"
        cursor = await db.execute(query, (limit,))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


@router.get("/unread-count")
async def get_unread_count():
    """Get count of unread notifications."""
    async with get_db() as db:
        cursor = await db.execute("SELECT COUNT(*) FROM notifications WHERE read = 0")
        row = await cursor.fetchone()
        return {"count": row[0] if row else 0}


@router.post("/{notification_id}/read")
async def mark_as_read(notification_id: int):
    """Mark a notification as read."""
    async with get_db() as db:
        cursor = await db.execute(
            "UPDATE notifications SET read = 1 WHERE id = ?",
            (notification_id,),
        )
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Notification not found")
        return {"status": "ok"}


@router.post("/mark-all-read")
async def mark_all_as_read():
    """Mark all notifications as read."""
    async with get_db() as db:
        await db.execute("UPDATE notifications SET read = 1 WHERE read = 0")
        await db.commit()
        return {"status": "ok"}
