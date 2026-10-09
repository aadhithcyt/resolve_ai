"""Debug script to understand mock interaction with agent loop."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.agent import run_agent


async def main():
    mock_tool_call = {
        "id": "call_123",
        "type": "function",
        "function": {
            "name": "get_ticket_info",
            "arguments": '{"ticket_id": 1}'
        }
    }

    mock_first = MagicMock()
    mock_first.choices = [MagicMock()]
    mock_first.choices[0].message.tool_calls = [mock_tool_call]
    mock_first.choices[0].message.content = None

    mock_second = MagicMock()
    mock_second.choices = [MagicMock()]
    mock_second.choices[0].message.tool_calls = None
    mock_second.choices[0].message.content = "I've looked into your account issue."

    call_count = 0

    async def mock_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        print(f"Call {call_count}")
        print(f"  tools in kwargs: {bool(kwargs.get('tools'))}")
        if call_count == 1:
            return mock_first
        return mock_second

    with patch("app.agent.call_groq", new=AsyncMock(side_effect=mock_call)):
        result = await run_agent(
            ticket_id=1,
            subject="Test",
            description="Test description",
            customer_name="Test User",
        )

    print(f"\nResult type: {type(result)}")
    print(f"Result keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
    print(f"Reply: {result.get('reply', 'N/A')[:100]}")
    print(f"Tool calls made: {result.get('tool_calls_made', 'N/A')}")
    print(f"Tools used: {result.get('tools_used', 'N/A')}")


asyncio.run(main())
