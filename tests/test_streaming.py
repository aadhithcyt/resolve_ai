"""Tests for streaming AI agent with SSE endpoint."""
import pytest
import pytest_asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.agent import run_agent_streaming


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_streaming_agent_yields_events(client):
    """Streaming agent should yield tool_call, tool_result, reply_chunk, and done events."""
    # Create customer + ticket
    cust = await client.post("/api/customers/", json={
        "name": "Stream Test",
        "email": "stream@test.com",
    })
    ticket = await client.post("/api/tickets/", json={
        "customer_id": cust.json()["id"],
        "subject": "Cannot access account",
        "description": "I can't log in after resetting my password",
    })
    ticket_id = ticket.json()["id"]

    # Mock Groq responses
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
                "content": "I've looked into your account issue. Please try clearing your browser cache.",
                "tool_calls": None
            },
            "finish_reason": "stop"
        }]
    }

    with patch("app.agent.call_groq", new=AsyncMock(side_effect=[mock_first_response, mock_second_response])):
        events = []
        async for event in run_agent_streaming(
            ticket_id=ticket_id,
            subject="Cannot access account",
            description="I can't log in after resetting my password",
            customer_name="Stream Test",
        ):
            events.append(event)

    # Verify event types
    event_types = [e["type"] for e in events]
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert "reply_chunk" in event_types
    assert "done" in event_types

    # Verify tool_call event
    tool_call_event = next(e for e in events if e["type"] == "tool_call")
    assert tool_call_event["data"]["tool_name"] == "get_ticket_info"
    assert "ticket_id" in tool_call_event["data"]["tool_args"]

    # Verify tool_result event
    tool_result_event = next(e for e in events if e["type"] == "tool_result")
    assert tool_result_event["data"]["tool_name"] == "get_ticket_info"
    assert "result" in tool_result_event["data"]

    # Verify reply_chunk events
    reply_chunks = [e for e in events if e["type"] == "reply_chunk"]
    assert len(reply_chunks) > 0
    full_reply = "".join(e["data"]["text"] for e in reply_chunks)
    assert "looked into" in full_reply

    # Verify done event
    done_event = next(e for e in events if e["type"] == "done")
    assert done_event["data"]["tool_calls_made"] >= 1
    assert "get_ticket_info" in done_event["data"]["tools_used"]


@pytest.mark.asyncio
async def test_streaming_agent_no_api_key(client):
    """Streaming agent should yield error and done events when API key is not configured."""
    with patch("app.agent.GROQ_API_KEY", ""):
        events = []
        async for event in run_agent_streaming(
            ticket_id=1,
            subject="Test",
            description="Test description",
            customer_name="Test",
        ):
            events.append(event)

    event_types = [e["type"] for e in events]
    assert "error" in event_types
    assert "done" in event_types

    error_event = next(e for e in events if e["type"] == "error")
    assert "GROQ_API_KEY" in error_event["data"]["error"]


@pytest.mark.asyncio
async def test_streaming_agent_max_iterations(client):
    """Streaming agent should handle max iterations gracefully."""
    cust = await client.post("/api/customers/", json={
        "name": "Max Iter Test",
        "email": "maxiter@test.com",
    })
    ticket = await client.post("/api/tickets/", json={
        "customer_id": cust.json()["id"],
        "subject": "Max iter test",
        "description": "Testing max iterations",
    })
    ticket_id = ticket.json()["id"]

    # Always return tool calls to hit max iterations
    mock_tool_call = {
        "id": "call_loop",
        "type": "function",
        "function": {
            "name": "get_ticket_info",
            "arguments": '{"ticket_id": ' + str(ticket_id) + '}'
        }
    }

    mock_response = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [mock_tool_call]
            },
            "finish_reason": "tool_calls"
        }]
    }

    with patch("app.agent.call_groq", new=AsyncMock(return_value=mock_response)):
        events = []
        async for event in run_agent_streaming(
            ticket_id=ticket_id,
            subject="Max iter test",
            description="Testing max iterations",
            customer_name="Max Iter Test",
        ):
            events.append(event)

    event_types = [e["type"] for e in events]
    assert "done" in event_types

    done_event = next(e for e in events if e["type"] == "done")
    assert "max iterations" in done_event["data"]["reasoning"].lower()


@pytest.mark.asyncio
async def test_streaming_agent_api_error(client):
    """Streaming agent should yield error event on API failure."""
    cust = await client.post("/api/customers/", json={
        "name": "Error Test",
        "email": "error@test.com",
    })
    ticket = await client.post("/api/tickets/", json={
        "customer_id": cust.json()["id"],
        "subject": "Error test",
        "description": "Testing error handling",
    })
    ticket_id = ticket.json()["id"]

    import httpx

    with patch("app.agent.call_groq", new=AsyncMock(side_effect=httpx.HTTPStatusError(
        "Rate limited", request=MagicMock(), response=MagicMock(status_code=429)
    ))):
        events = []
        async for event in run_agent_streaming(
            ticket_id=ticket_id,
            subject="Error test",
            description="Testing error handling",
            customer_name="Error Test",
        ):
            events.append(event)

    event_types = [e["type"] for e in events]
    assert "error" in event_types
    assert "done" in event_types

    error_event = next(e for e in events if e["type"] == "error")
    assert "429" in error_event["data"]["error"]


@pytest.mark.asyncio
async def test_sse_stream_endpoint_exists(client):
    """SSE stream endpoint should be accessible."""
    cust = await client.post("/api/customers/", json={
        "name": "SSE Test",
        "email": "sse@test.com",
    })
    ticket = await client.post("/api/tickets/", json={
        "customer_id": cust.json()["id"],
        "subject": "SSE test",
        "description": "Testing SSE endpoint",
    })
    ticket_id = ticket.json()["id"]

    mock_response = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "Test reply from SSE endpoint",
                "tool_calls": None
            },
            "finish_reason": "stop"
        }]
    }

    with patch("app.agent.call_groq", new=AsyncMock(return_value=mock_response)):
        resp = await client.post("/api/ai/agent/stream", json={
            "ticket_id": ticket_id,
        })
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_sse_stream_endpoint_ticket_not_found(client):
    """SSE stream endpoint should return 404 for non-existent ticket."""
    resp = await client.post("/api/ai/agent/stream", json={
        "ticket_id": 99999,
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_sse_stream_endpoint_yields_events(client):
    """SSE stream endpoint should yield properly formatted SSE events."""
    cust = await client.post("/api/customers/", json={
        "name": "SSE Events Test",
        "email": "sse_events@test.com",
    })
    ticket = await client.post("/api/tickets/", json={
        "customer_id": cust.json()["id"],
        "subject": "SSE events test",
        "description": "Testing SSE event format",
    })
    ticket_id = ticket.json()["id"]

    mock_tool_call = {
        "id": "call_sse",
        "type": "function",
        "function": {
            "name": "get_ticket_info",
            "arguments": '{"ticket_id": ' + str(ticket_id) + '}'
        }
    }

    mock_first = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [mock_tool_call]
            },
            "finish_reason": "tool_calls"
        }]
    }

    mock_second = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "Here is your answer.",
                "tool_calls": None
            },
            "finish_reason": "stop"
        }]
    }

    with patch("app.agent.call_groq", new=AsyncMock(side_effect=[mock_first, mock_second])):
        resp = await client.post("/api/ai/agent/stream", json={
            "ticket_id": ticket_id,
        })
        assert resp.status_code == 200

        body = resp.text
        # Check SSE format
        assert "event: tool_call" in body
        assert "event: tool_result" in body
        assert "event: reply_chunk" in body
        assert "event: done" in body

        # Verify data lines are valid JSON
        for line in body.split("\n"):
            if line.startswith("data: "):
                data_str = line[6:]
                try:
                    json.loads(data_str)
                except json.JSONDecodeError:
                    pytest.fail(f"Invalid JSON in SSE data: {data_str}")
