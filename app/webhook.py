"""Webhook integrations for Slack, Discord, and Teams notifications."""
import json
import logging
import hmac
import hashlib
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


class SlackWebhook(BaseModel):
    url: str = Field(..., description="Slack incoming webhook URL")


class DiscordWebhook(BaseModel):
    url: str = Field(..., description="Discord webhook URL")


class TeamsWebhook(BaseModel):
    url: str = Field(..., description="Teams webhook URL")


async def send_slack_notification(webhook_url: str, ticket_data: dict) -> bool:
    """Send a ticket notification to Slack."""
    try:
        payload = {
            "text": f"New Support Ticket #{ticket_data.get('id')}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Ticket #{ticket_data.get('id')}* — {ticket_data.get('subject', 'N/A')}"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Status:* {ticket_data.get('status', 'N/A')}"},
                        {"type": "mrkdwn", "text": f"*Priority:* {ticket_data.get('priority', 'N/A')}"},
                        {"type": "mrkdwn", "text": f"*Category:* {ticket_data.get('category', 'N/A')}"},
                        {"type": "mrkdwn", "text": f"*Customer:* {ticket_data.get('customer_name', 'N/A')}"}
                    ]
                }
            ]
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)
            return resp.status_code == 200
    except Exception as e:
        logger.error(f"Slack webhook error: {e}")
        return False


async def send_discord_notification(webhook_url: str, ticket_data: dict) -> bool:
    """Send a ticket notification to Discord."""
    try:
        payload = {
            "content": f"New Support Ticket #{ticket_data.get('id')}",
            "embeds": [{
                "title": f"Ticket #{ticket_data.get('id')} — {ticket_data.get('subject', 'N/A')}",
                "color": 0x6366f1,
                "fields": [
                    {"name": "Status", "value": ticket_data.get('status', 'N/A'), "inline": True},
                    {"name": "Priority", "value": ticket_data.get('priority', 'N/A'), "inline": True},
                    {"name": "Category", "value": ticket_data.get('category', 'N/A'), "inline": True},
                    {"name": "Customer", "value": ticket_data.get('customer_name', 'N/A'), "inline": True}
                ]
            }]
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)
            return resp.status_code in (200, 204)
    except Exception as e:
        logger.error(f"Discord webhook error: {e}")
        return False


async def send_teams_notification(webhook_url: str, ticket_data: dict) -> bool:
    """Send a ticket notification to Microsoft Teams."""
    try:
        payload = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "themeColor": "6366f1",
            "summary": f"New Support Ticket #{ticket_data.get('id')}",
            "sections": [{
                "activityTitle": f"Ticket #{ticket_data.get('id')} — {ticket_data.get('subject', 'N/A')}",
                "facts": [
                    {"name": "Status", "value": ticket_data.get('status', 'N/A')},
                    {"name": "Priority", "value": ticket_data.get('priority', 'N/A')},
                    {"name": "Category", "value": ticket_data.get('category', 'N/A')},
                    {"name": "Customer", "value": ticket_data.get('customer_name', 'N/A')}
                ]
            }]
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)
            return resp.status_code == 200
    except Exception as e:
        logger.error(f"Teams webhook error: {e}")
        return False


@router.post("/slack")
async def register_slack_webhook(webhook: SlackWebhook):
    """Register a Slack webhook URL for ticket notifications."""
    # In production, store this in database
    return {"status": "registered", "type": "slack", "url": webhook.url[:30] + "..."}


@router.post("/discord")
async def register_discord_webhook(webhook: DiscordWebhook):
    """Register a Discord webhook URL for ticket notifications."""
    return {"status": "registered", "type": "discord", "url": webhook.url[:30] + "..."}


@router.post("/teams")
async def register_teams_webhook(webhook: TeamsWebhook):
    """Register a Teams webhook URL for ticket notifications."""
    return {"status": "registered", "type": "teams", "url": webhook.url[:30] + "..."}


@router.post("/test/{webhook_type}")
async def test_webhook(webhook_type: str, request: Request):
    """Test a webhook by sending a test notification."""
    body = await request.json()
    url = body.get("url", "")
    if not url:
        raise HTTPException(status_code=400, detail="URL required")

    test_data = {
        "id": 999,
        "subject": "Test Ticket",
        "status": "open",
        "priority": "medium",
        "category": "general",
        "customer_name": "Test Customer",
    }

    if webhook_type == "slack":
        result = await send_slack_notification(url, test_data)
    elif webhook_type == "discord":
        result = await send_discord_notification(url, test_data)
    elif webhook_type == "teams":
        result = await send_teams_notification(url, test_data)
    else:
        raise HTTPException(status_code=400, detail="Invalid webhook type")

    return {"status": "sent" if result else "failed", "type": webhook_type}
