"""AI agent loop with tool calling for ResolveAI."""
import json
import logging
from typing import Any, AsyncGenerator

import httpx

from .config import GROQ_API_KEY, GROQ_MODEL
from .tools import TOOL_DEFINITIONS, ToolExecutor
from .memory import save_memory, get_memory, get_conversation_context
from .cache import get_cached_response, cache_response

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 5


async def call_groq(messages: list, tools: list = None, temperature: float = 0.7) -> Any:
    """Call Groq API with messages and optional tool definitions. Uses caching."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not configured")

    # Check cache first
    cached = get_cached_response(messages, tools, temperature)
    if cached is not None:
        return cached

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
        result = resp.json()
        # Cache the response
        cache_response(messages, result, tools, temperature)
        return result


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

    # Fetch customer_id and attachment info for context
    from .database import get_db
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT customer_id FROM tickets WHERE id = ?", (ticket_id,)
        )
        row = await cursor.fetchone()
        actual_customer_id = row["customer_id"] if row else 0

        cursor = await db.execute(
            "SELECT filename, content_type FROM attachments WHERE ticket_id = ? ORDER BY uploaded_at DESC",
            (ticket_id,),
        )
        attachments = [dict(r) for r in await cursor.fetchall()]

    attachment_context = ""
    if attachments:
        attachment_list = ", ".join(a["filename"] for a in attachments)
        attachment_context = f"- Attachments: {attachment_list}\n"

    # Load conversation context from memory
    conversation_context = await get_conversation_context(actual_customer_id)

    # Load relevant memories
    last_reply_strategy = await get_memory(actual_customer_id, "last_reply_strategy")
    escalation_history = await get_memory(actual_customer_id, "escalation_history")
    common_issues = await get_memory(actual_customer_id, "common_issues")

    # Build conversation history section for system prompt
    conversation_history_text = ""
    if conversation_context:
        lines = []
        for t in conversation_context:
            lines.append(f"  Ticket #{t['id']}: {t['subject']} (status: {t['status']}, priority: {t['priority']})")
            for msg in t.get("messages", []):
                sender_label = msg["sender"].capitalize()
                lines.append(f"    {sender_label}: {msg['content'][:200]}")
        conversation_history_text = "\n".join(lines)

    memory_context_text = ""
    if last_reply_strategy:
        memory_context_text += f"\n- Last reply strategy: {last_reply_strategy}"
    if escalation_history:
        memory_context_text += f"\n- Escalation history: {escalation_history}"
    if common_issues:
        memory_context_text += f"\n- Common issues: {common_issues}"

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
{attachment_context}"""

    # Add conversation history to system prompt
    if conversation_history_text:
        system_prompt += f"\nConversation history with this customer:\n{conversation_history_text}\n"

    # Add memory context to system prompt
    if memory_context_text:
        system_prompt += f"\nAgent memory for this customer:{memory_context_text}\n"

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

            # Save agent decisions to memory
            try:
                # Determine reply strategy based on tool usage
                if "escalate_ticket" in tools_used:
                    reply_strategy = "escalated"
                elif "search_knowledge_base" in tools_used:
                    reply_strategy = "knowledge_base_lookup"
                elif "get_customer_info" in tools_used:
                    reply_strategy = "personalized_reply"
                else:
                    reply_strategy = "general_reply"

                await save_memory(
                    ticket_id=ticket_id,
                    customer_id=actual_customer_id,
                    key="last_reply_strategy",
                    value=reply_strategy,
                )

                # Track escalation history
                if "escalate_ticket" in tools_used:
                    escalation_entry = f"Ticket #{ticket_id}: escalated ({subject})"
                    existing = await get_memory(actual_customer_id, "escalation_history")
                    if existing:
                        new_history = f"{existing}; {escalation_entry}"
                    else:
                        new_history = escalation_entry
                    await save_memory(
                        ticket_id=ticket_id,
                        customer_id=actual_customer_id,
                        key="escalation_history",
                        value=new_history,
                    )

                # Track common issues
                if category and category != "general":
                    existing_issues = await get_memory(actual_customer_id, "common_issues")
                    if existing_issues:
                        issues_list = existing_issues.split(", ")
                        if category not in issues_list:
                            issues_list.append(category)
                        new_issues = ", ".join(issues_list)
                    else:
                        new_issues = category
                    await save_memory(
                        ticket_id=ticket_id,
                        customer_id=actual_customer_id,
                        key="common_issues",
                        value=new_issues,
                    )
            except Exception as mem_err:
                logger.warning(f"Failed to save agent memory: {mem_err}")

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


async def run_agent_streaming(
    ticket_id: int,
    subject: str,
    description: str,
    customer_name: str,
    category: str = "general",
) -> AsyncGenerator[dict, None]:
    """Run the AI agent loop with streaming events.

    Yields dicts with the following types:
    - {"type": "tool_call", "data": {"tool_name": str, "tool_args": dict, "tool_call_id": str}}
    - {"type": "tool_result", "data": {"tool_name": str, "result": dict}}
    - {"type": "reply_chunk", "data": {"text": str}}
    - {"type": "done", "data": {"reply": str, "tool_calls_made": int, "tools_used": list, "reasoning": str}}
    - {"type": "error", "data": {"error": str}}

    """
    if not GROQ_API_KEY:
        yield {
            "type": "error",
            "data": {"error": "GROQ_API_KEY not configured"}
        }
        yield {
            "type": "done",
            "data": {
                "reply": "[AI agent unavailable — GROQ_API_KEY not configured]",
                "tool_calls_made": 0,
                "tools_used": [],
                "reasoning": "API key not configured",
            }
        }
        return

    executor = ToolExecutor()
    tools_used = []
    tool_calls_made = 0

    # Fetch customer_id and attachment info for context
    from .database import get_db
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT customer_id FROM tickets WHERE id = ?", (ticket_id,)
        )
        row = await cursor.fetchone()
        actual_customer_id = row["customer_id"] if row else 0

        cursor = await db.execute(
            "SELECT filename, content_type FROM attachments WHERE ticket_id = ? ORDER BY uploaded_at DESC",
            (ticket_id,),
        )
        attachments = [dict(r) for r in await cursor.fetchall()]

    attachment_context = ""
    if attachments:
        attachment_list = ", ".join(a["filename"] for a in attachments)
        attachment_context = f"- Attachments: {attachment_list}\n"

    # Load conversation context from memory
    conversation_context = await get_conversation_context(actual_customer_id)

    # Load relevant memories
    last_reply_strategy = await get_memory(actual_customer_id, "last_reply_strategy")
    escalation_history = await get_memory(actual_customer_id, "escalation_history")
    common_issues = await get_memory(actual_customer_id, "common_issues")

    # Build conversation history section for system prompt
    conversation_history_text = ""
    if conversation_context:
        lines = []
        for t in conversation_context:
            lines.append(f"  Ticket #{t['id']}: {t['subject']} (status: {t['status']}, priority: {t['priority']})")
            for msg in t.get("messages", []):
                sender_label = msg["sender"].capitalize()
                lines.append(f"    {sender_label}: {msg['content'][:200]}")
        conversation_history_text = "\n".join(lines)

    memory_context_text = ""
    if last_reply_strategy:
        memory_context_text += f"\n- Last reply strategy: {last_reply_strategy}"
    if escalation_history:
        memory_context_text += f"\n- Escalation history: {escalation_history}"
    if common_issues:
        memory_context_text += f"\n- Common issues: {common_issues}"

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
{attachment_context}"""

    if conversation_history_text:
        system_prompt += f"\nConversation history with this customer:\n{conversation_history_text}\n"
    if memory_context_text:
        system_prompt += f"\nAgent memory for this customer:{memory_context_text}\n"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Please help resolve ticket #{ticket_id}: {subject}\n\nCustomer message: {description}"},
    ]

    final_reply = ""

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

                for tc in msg["tool_calls"]:
                    tool_name = tc["function"]["name"]
                    try:
                        tool_args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        tool_args = {}

                    tools_used.append(tool_name)

                    # Emit tool_call event
                    yield {
                        "type": "tool_call",
                        "data": {
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                            "tool_call_id": tc["id"],
                        }
                    }

                    result = await executor.execute(tool_name, tool_args)

                    # Emit tool_result event
                    yield {
                        "type": "tool_result",
                        "data": {
                            "tool_name": tool_name,
                            "result": result,
                        }
                    }

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tool_name,
                        "content": json.dumps(result),
                    })

                continue  # Next iteration with tool results

            # No tool calls — this is the final response
            final_reply = msg.get("content", "")

            # Save agent decisions to memory
            try:
                if "escalate_ticket" in tools_used:
                    reply_strategy = "escalated"
                elif "search_knowledge_base" in tools_used:
                    reply_strategy = "knowledge_base_lookup"
                elif "get_customer_info" in tools_used:
                    reply_strategy = "personalized_reply"
                else:
                    reply_strategy = "general_reply"

                await save_memory(
                    ticket_id=ticket_id,
                    customer_id=actual_customer_id,
                    key="last_reply_strategy",
                    value=reply_strategy,
                )

                if "escalate_ticket" in tools_used:
                    escalation_entry = f"Ticket #{ticket_id}: escalated ({subject})"
                    existing = await get_memory(actual_customer_id, "escalation_history")
                    if existing:
                        new_history = f"{existing}; {escalation_entry}"
                    else:
                        new_history = escalation_entry
                    await save_memory(
                        ticket_id=ticket_id,
                        customer_id=actual_customer_id,
                        key="escalation_history",
                        value=new_history,
                    )

                if category and category != "general":
                    existing_issues = await get_memory(actual_customer_id, "common_issues")
                    if existing_issues:
                        issues_list = existing_issues.split(", ")
                        if category not in issues_list:
                            issues_list.append(category)
                        new_issues = ", ".join(issues_list)
                    else:
                        new_issues = category
                    await save_memory(
                        ticket_id=ticket_id,
                        customer_id=actual_customer_id,
                        key="common_issues",
                        value=new_issues,
                    )
            except Exception as mem_err:
                logger.warning(f"Failed to save agent memory: {mem_err}")

            # Stream the reply in chunks
            if final_reply:
                chunk_size = 20
                for i in range(0, len(final_reply), chunk_size):
                    chunk = final_reply[i:i + chunk_size]
                    yield {
                        "type": "reply_chunk",
                        "data": {"text": chunk}
                    }

            yield {
                "type": "done",
                "data": {
                    "reply": final_reply,
                    "tool_calls_made": tool_calls_made,
                    "tools_used": list(set(tools_used)),
                    "reasoning": f"Completed in {iteration + 1} iterations",
                }
            }
            return

        except httpx.HTTPStatusError as e:
            logger.error(f"Groq API error: {e.response.status_code}")
            error_msg = f"[AI agent failed: {e.response.status_code} — check your Groq API key and quota]"
            yield {
                "type": "error",
                "data": {"error": error_msg}
            }
            yield {
                "type": "done",
                "data": {
                    "reply": error_msg,
                    "tool_calls_made": tool_calls_made,
                    "tools_used": list(set(tools_used)),
                    "reasoning": f"API error: {e.response.status_code}",
                }
            }
            return
        except Exception as e:
            logger.error(f"Agent error: {e}")
            error_msg = f"[AI agent failed: {str(e)}]"
            yield {
                "type": "error",
                "data": {"error": error_msg}
            }
            yield {
                "type": "done",
                "data": {
                    "reply": error_msg,
                    "tool_calls_made": tool_calls_made,
                    "tools_used": list(set(tools_used)),
                    "reasoning": f"Error: {str(e)}",
                }
            }
            return

    # Max iterations reached
    max_iter_msg = "[AI agent reached maximum iterations without completing. Please try again or escalate manually.]"
    yield {
        "type": "error",
        "data": {"error": max_iter_msg}
    }
    yield {
        "type": "done",
        "data": {
            "reply": max_iter_msg,
            "tool_calls_made": tool_calls_made,
            "tools_used": list(set(tools_used)),
            "reasoning": f"Max iterations ({MAX_ITERATIONS}) reached",
        }
    }
