"""Spike: Validate Groq tool calling for ResolveAI agent loop.

Given a customer support ticket, when the LLM is given tool definitions,
then it should return structured tool_calls that we can execute locally.
"""
import httpx
import json
import os
import sys

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("RESOLVEAI_MODEL", "openai/gpt-oss-120b")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_ticket_info",
            "description": "Get detailed information about a support ticket",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ticket ID to look up"
                    }
                },
                "required": ["ticket_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_info",
            "description": "Get customer details including contact info and history",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "integer",
                        "description": "The customer ID to look up"
                    }
                },
                "required": ["customer_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "Search the knowledge base for relevant articles, FAQs, and solutions",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for the knowledge base"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_ticket",
            "description": "Escalate a ticket to a higher priority or different team",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ticket ID to escalate"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for escalation"
                    },
                    "new_priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "urgent"],
                        "description": "New priority level"
                    }
                },
                "required": ["ticket_id", "reason", "new_priority"]
            }
        }
    }
]


def test_tool_calling():
    """Test that Groq returns tool_calls for a support scenario."""
    if not GROQ_API_KEY:
        print("SKIP: GROQ_API_KEY not set")
        return

    messages = [
        {
            "role": "system",
            "content": "You are a customer support AI agent. Use the available tools to gather information before responding to the customer. Always check the ticket details and search the knowledge base before drafting a reply."
        },
        {
            "role": "user",
            "content": "Customer John Doe (ID: 1) has ticket #42 about 'Cannot access my account after password reset'. The customer is frustrated. Help me resolve this."
        }
    ]

    print("=== Test 1: Tool calling with tool_choice=auto ===")
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": messages,
                    "tools": TOOLS,
                    "tool_choice": "auto",
                    "temperature": 0.1,
                    "max_tokens": 1000,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            choice = data["choices"][0]
            msg = choice["message"]
            finish_reason = choice["finish_reason"]

            print(f"Finish reason: {finish_reason}")
            print(f"Message role: {msg['role']}")

            if "tool_calls" in msg and msg["tool_calls"]:
                print(f"\nTool calls returned: {len(msg['tool_calls'])}")
                for tc in msg["tool_calls"]:
                    print(f"  - {tc['function']['name']}({tc['function']['arguments']})")

                # Simulate executing tools and sending results back
                tool_results = []
                for tc in msg["tool_calls"]:
                    tool_name = tc["function"]["name"]
                    args = json.loads(tc["function"]["arguments"])
                    # Mock execution
                    result = f"Mock result for {tool_name} with args {args}"
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tool_name,
                        "content": result,
                    })

                # Second call with tool results
                messages.append(msg)
                messages.extend(tool_results)

                print("\n=== Test 2: Follow-up with tool results ===")
                resp2 = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": GROQ_MODEL,
                        "messages": messages,
                        "tools": TOOLS,
                        "tool_choice": "auto",
                        "temperature": 0.7,
                        "max_tokens": 500,
                    },
                )
                resp2.raise_for_status()
                data2 = resp2.json()
                final_msg = data2["choices"][0]["message"]
                final_content = final_msg.get("content", "")
                if final_content:
                    print(f"Final response: {final_content[:200]}...")
                else:
                    print(f"Final message has no content. Keys: {list(final_msg.keys())}")
                    if "tool_calls" in final_msg:
                        print(f"Additional tool calls: {len(final_msg['tool_calls'])}")
                print(f"Final finish reason: {data2['choices'][0]['finish_reason']}")

                print("\n=== VERDICT: VALIDATED ===")
                print("Groq tool calling works. Agent loop is feasible.")
            else:
                print(f"No tool calls. Content: {msg.get('content', 'N/A')[:200]}")
                print("\n=== VERDICT: PARTIAL ===")
                print("Model didn't call tools. May need prompt tuning.")

    except httpx.HTTPStatusError as e:
        print(f"HTTP Error: {e.response.status_code}")
        print(f"Response: {e.response.text[:500]}")
        print("\n=== VERDICT: NEEDS INVESTIGATION ===")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print("\n=== VERDICT: ERROR ===")


if __name__ == "__main__":
    test_tool_calling()
