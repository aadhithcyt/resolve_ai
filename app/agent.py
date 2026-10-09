"""AI agent loop with tool calling for ResolveAI."""
import json
import logging
from typing import Any

import httpx

from .config import GROQ_API_KEY, GROQ_MODEL
from .tools import TOOL_DEFINITIONS, ToolExecutor

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 5


async def call_groq(messages: list, tools: list = None, temperature: float = 0.7) -> Any:
    """Call Groq API with messages and optional tool definitions."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not configured")

    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 1000,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


async def run_agent(
    ticket_id: int,
    subject: str,
    description: str,
    customer_name: str,
    category: str = "general",
) -> dict:
    """Run the AI agent loop for a support ticket.

    The agent:
    1. Receives the ticket context
    2. Decides which tools to call (get info, search KB, escalate, etc.)
    3. Executes tools and feeds results back
    4. Produces a final reply

    Returns dict with reply, tool_calls_made, tools_used, and reasoning.
    """
    if not GROQ_API_KEY:
        return {
            "reply": "[AI agent unavailable — GROQ_API_KEY not configured]",
            "tool_calls_made": 0,
            "tools_used": [],
            "reasoning": "API key not configured",
        }

    executor = ToolExecutor()
    tools_used = []
    tool_calls_made = 0

    system_prompt = f"""You are an AI customer support agent for ResolveAI. You are helping resolve a support ticket.

Your goal is to:
1. Gather information about the ticket and customer using the available tools
2. Search the knowledge base for relevant solutions
3. Draft a helpful, empathetic reply to the customer
4. Escalate if the issue is critical or the customer is very upset

Available tools:
- get_ticket_info: Get ticket details
- get_customer_info: Get customer details and history
- search_knowledge_base: Search for solutions and FAQs
- escalate_ticket: Escalate to higher priority
- add_ticket_note: Add internal notes

Rules:
- Always check the ticket info first
- Search the knowledge base before drafting a reply
- If the customer is very frustrated or the issue is critical, escalate
- Keep replies under 200 words
- Be empathetic and professional
- Do not make promises you cannot keep
- If you need more information, ask specific questions

Ticket context:
- Ticket ID: {ticket_id}
- Customer: {customer_name}
- Subject: {subject}
- Description: {description}
- Category: {category}
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Please help resolve ticket #{ticket_id}: {subject}\n\nCustomer message: {description}"},
    ]

    for iteration in range(MAX_ITERATIONS):
        try:
            response = await call_groq(messages, tools=TOOL_DEFINITIONS, temperature=0.1 if iteration == 0 else 0.7)

            choice = response["choices"][0]
            msg = choice["message"]
            finish_reason = choice["finish_reason"]

            # Check for tool calls
            if "tool_calls" in msg and msg["tool_calls"]:
                tool_calls_made += len(msg["tool_calls"])
                messages.append(msg)

                # Execute each tool call
                for tc in msg["tool_calls"]:
                    tool_name = tc["function"]["name"]
                    try:
                        tool_args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        tool_args = {}

                    tools_used.append(tool_name)
                    result = await executor.execute(tool_name, tool_args)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tool_name,
                        "content": json.dumps(result),
                    })

                continue  # Next iteration with tool results

            # No tool calls — this is the final response
            final_reply = msg.get("content", "")
            return {
                "reply": final_reply,
                "tool_calls_made": tool_calls_made,
                "tools_used": list(set(tools_used)),
                "reasoning": f"Completed in {iteration + 1} iterations",
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"Groq API error: {e.response.status_code}")
            return {
                "reply": f"[AI agent failed: {e.response.status_code} — check your Groq API key and quota]",
                "tool_calls_made": tool_calls_made,
                "tools_used": list(set(tools_used)),
                "reasoning": f"API error: {e.response.status_code}",
            }
        except Exception as e:
            logger.error(f"Agent error: {e}")
            return {
                "reply": f"[AI agent failed: {str(e)}]",
                "tool_calls_made": tool_calls_made,
                "tools_used": list(set(tools_used)),
                "reasoning": f"Error: {str(e)}",
            }

    # Max iterations reached
    return {
        "reply": "[AI agent reached maximum iterations without completing. Please try again or escalate manually.]",
        "tool_calls_made": tool_calls_made,
        "tools_used": list(set(tools_used)),
        "reasoning": f"Max iterations ({MAX_ITERATIONS}) reached",
    }
