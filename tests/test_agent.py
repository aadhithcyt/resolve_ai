"""Tests for agent loop with tool calling."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.agent import run_agent, ToolExecutor
from app.tools import TOOL_DEFINITIONS


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_agent_loop_with_tool_calling(client):
    """Agent should use tools and produce a reply for a support ticket."""
    # Create customer + ticket
    cust = await client.post("/api/customers/", json={
        "name": "Agent Test",
        "email": "agent@test.com",
    })
    ticket = await client.post("/api/tickets/", json={
        "customer_id": cust.json()["id"],
        "subject": "Cannot access account",
        "description": "I can't log in after resetting my password",
    })
    ticket_id = ticket.json()["id"]

    # Mock Groq tool calling response - use dict-like structure
    mock_tool_call = {
        "id": "call_123",
        "type": "function",
        "function": {
            "name": "get_ticket_info",
            "arguments": '{"ticket_id": ' + str(ticket_id) + '}'
        }
    }

    mock_first_response = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [mock_tool_call]
            },
            "finish_reason": "tool_calls"
        }]
    }

    mock_second_response = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "I've looked into your account issue. Please try clearing your browser cache and using the password reset link again.",
                "tool_calls": None
            },
            "finish_reason": "stop"
        }]
    }

    with patch("app.agent.call_groq", new=AsyncMock(side_effect=[mock_first_response, mock_second_response])):
        result = await run_agent(
            ticket_id=ticket_id,
            subject="Cannot access account",
            description="I can't log in after resetting my password",
            customer_name="Agent Test",
        )

    assert "reply" in result
    assert "I've looked into" in result["reply"]
    assert "tool_calls_made" in result
    assert result["tool_calls_made"] >= 1


@pytest.mark.asyncio
async def test_tool_definitions_valid():
    """All tool definitions should have required fields."""
    assert len(TOOL_DEFINITIONS) > 0
    for tool in TOOL_DEFINITIONS:
        assert "type" in tool
        assert "function" in tool
        assert "name" in tool["function"]
        assert "description" in tool["function"]
        assert "parameters" in tool["function"]


@pytest.mark.asyncio
async def test_execute_tool_dispatch():
    """Tool executor should dispatch to correct tool function."""
    executor = ToolExecutor()

    mock_fn = AsyncMock(return_value={"id": 1, "subject": "Test"})
    executor.tools["get_ticket_info"] = mock_fn
    result = await executor.execute("get_ticket_info", {"ticket_id": 1})
    assert result["id"] == 1
    assert result["subject"] == "Test"
    mock_fn.assert_called_once_with(ticket_id=1)


@pytest.mark.asyncio
async def test_execute_tool_unknown():
    """Tool executor should handle unknown tool gracefully."""
    executor = ToolExecutor()
    result = await executor.execute("nonexistent_tool", {})
    assert "error" in result


@pytest.mark.asyncio
async def test_agent_endpoint_exists(client):
    """Agent endpoint should be accessible."""
    # Create customer + ticket
    cust = await client.post("/api/customers/", json={
        "name": "Agent Endpoint",
        "email": "agent_ep@test.com",
    })
    ticket = await client.post("/api/tickets/", json={
        "customer_id": cust.json()["id"],
        "subject": "Agent endpoint test",
        "description": "Testing agent endpoint",
    })
    ticket_id = ticket.json()["id"]

    with patch("app.agent.run_agent", new=AsyncMock(return_value={
        "reply": "Test reply",
        "tool_calls_made": 2,
        "tools_used": ["get_ticket_info", "search_knowledge_base"],
    })):
        resp = await client.post("/api/ai/agent", json={
            "ticket_id": ticket_id,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        assert "tool_calls_made" in data
