"""Groq AI integration for auto-replies and sentiment analysis."""
import httpx
import json
from .config import GROQ_API_KEY, GROQ_MODEL


async def analyze_sentiment(text: str) -> dict:
    """Analyze sentiment of customer message using Groq."""
    if not GROQ_API_KEY:
        return {"sentiment": "neutral", "confidence": 0.5}

    prompt = f"""Analyze the sentiment of this customer support message. Respond with ONLY a JSON object in this exact format: {{"sentiment": "positive|neutral|negative", "confidence": 0.0-1.0}}

Message: {text[:2000]}"""

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
                    "max_tokens": 100,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            # Extract JSON from response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
    except Exception:
        pass

    return {"sentiment": "neutral", "confidence": 0.5}


async def generate_reply(
    subject: str,
    description: str,
    customer_name: str,
    tone: str = "professional",
    category: str = "general",
) -> str:
    """Generate an AI-powered support reply draft."""
    if not GROQ_API_KEY:
        return (
            "[AI reply unavailable — GROQ_API_KEY not configured. "
            "Set it in your environment to enable AI features.]"
        )

    tone_instructions = {
        "professional": "Be professional, clear, and solution-oriented.",
        "friendly": "Be warm, friendly, and approachable.",
        "empathetic": "Show empathy and understanding first, then offer solutions.",
        "concise": "Be brief and to the point. Max 3-4 sentences.",
    }

    prompt = f"""You are a customer support agent. Draft a reply to the following support ticket.

Customer: {customer_name}
Category: {category}
Subject: {subject}
Message: {description[:2000]}

{tone_instructions.get(tone, tone_instructions['professional'])}

Rules:
- Do not make promises you cannot keep
- If you need more information, ask specific questions
- Keep it under 200 words
- Do not include subject line or greeting like "Dear..." — just the body of the reply
- Do not include any markdown formatting

Reply:"""

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
                    "temperature": 0.7,
                    "max_tokens": 500,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except httpx.HTTPStatusError as e:
        return f"[AI reply failed: {e.response.status_code} — check your Groq API key and quota]"
    except Exception as e:
        return f"[AI reply failed: {str(e)}]"
