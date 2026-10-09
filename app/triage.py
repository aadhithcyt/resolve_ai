"""Auto-triage: AI classification of ticket category and priority."""
import json
import logging
from typing import Optional

import httpx

from .config import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)

CATEGORIES = [
    "general",
    "billing",
    "technical",
    "account",
    "shipping",
    "returns",
    "product_issue",
    "feature_request",
]

PRIORITIES = ["low", "medium", "high", "urgent"]


async def classify_ticket(subject: str, description: str) -> dict:
    """Classify a ticket's category and priority using Groq.

    Returns dict with: category, priority, confidence, reasoning
    """
    if not GROQ_API_KEY:
        return {
            "category": "general",
            "priority": "medium",
            "confidence": 0.0,
            "reasoning": "AI not configured",
        }

    prompt = f"""Classify this support ticket. Respond with ONLY a JSON object in this exact format: {{"category": "one of {CATEGORIES}", "priority": "one of {PRIORITIES}", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}

Subject: {subject}
Description: {description[:1000]}"""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 200,
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(content[start:end])
                # Validate
                if result.get("category") not in CATEGORIES:
                    result["category"] = "general"
                if result.get("priority") not in PRIORITIES:
                    result["priority"] = "medium"
                return result
    except Exception as e:
        logger.error(f"Auto-triage classification failed: {e}")

    return {
        "category": "general",
        "priority": "medium",
        "confidence": 0.0,
        "reasoning": "Classification failed",
    }
