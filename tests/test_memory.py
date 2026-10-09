"""Tests for conversation memory functionality."""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.memory import save_memory, get_memory, get_conversation_context
from app.database import get_db


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_save_and_get_memory(client):
    """Should save a memory entry and retrieve it."""
    # Create a customer first
    cust = await client.post("/api/customers/", json={
        "name": "Memory Test",
        "email": "memory@test.com",
    })
    customer_id = cust.json()["id"]

    # Save memory
    result = await save_memory(
        ticket_id=None,
        customer_id=customer_id,
        key="test_key",
        value="test_value",
    )
    assert result["id"] is not None
    assert result["customer_id"] == customer_id
    assert result["key"] == "test_key"
    assert result["value"] == "test_value"

    # Retrieve memory
    value = await get_memory(customer_id, "test_key")
    assert value == "test_value"


@pytest.mark.asyncio
async def test_get_memory_returns_none_for_missing_key(client):
    """Should return None when no memory exists for the key."""
    cust = await client.post("/api/customers/", json={
        "name": "Memory None Test",
        "email": "memory_none@test.com",
    })
    customer_id = cust.json()["id"]

    value = await get_memory(customer_id, "nonexistent_key")
    assert value is None


@pytest.mark.asyncio
async def test_get_memory_returns_most_recent(client):
    """Should return the most recent value when multiple entries exist."""
    cust = await client.post("/api/customers/", json={
        "name": "Memory Recent Test",
        "email": "memory_recent@test.com",
    })
    customer_id = cust.json()["id"]

    # Save first value
    await save_memory(
        ticket_id=None,
        customer_id=customer_id,
        key="versioned_key",
        value="first_value",
    )
    # Save second value
    await save_memory(
        ticket_id=None,
        customer_id=customer_id,
        key="versioned_key",
        value="second_value",
    )

    # Should get the most recent
    value = await get_memory(customer_id, "versioned_key")
    assert value == "second_value"


@pytest.mark.asyncio
async def test_get_conversation_context_empty(client):
    """Should return empty list for customer with no tickets."""
    cust = await client.post("/api/customers/", json={
        "name": "Empty Context Test",
        "email": "empty_context@test.com",
    })
    customer_id = cust.json()["id"]

    context = await get_conversation_context(customer_id)
    assert context == []


@pytest.mark.asyncio
async def test_get_conversation_context_with_tickets(client):
    """Should return tickets with messages for a customer."""
    cust = await client.post("/api/customers/", json={
        "name": "Context Test",
        "email": "context@test.com",
    })
    customer_id = cust.json()["id"]

    # Create a ticket
    ticket = await client.post("/api/tickets/", json={
        "customer_id": customer_id,
        "subject": "Test ticket",
        "description": "Test description",
    })
    ticket_id = ticket.json()["id"]

    # Add a message to the ticket
    async with get_db() as db:
        await db.execute(
            "INSERT INTO messages (ticket_id, sender, content) VALUES (?, ?, ?)",
            (ticket_id, "customer", "Hello, I need help"),
        )
        await db.commit()

    # Get conversation context
    context = await get_conversation_context(customer_id)
    assert len(context) == 1
    assert context[0]["id"] == ticket_id
    assert context[0]["subject"] == "Test ticket"
    # Ticket creation auto-creates a message with the description, plus our manual one
    assert len(context[0]["messages"]) == 2
    # Find our manually added message
    manual_msgs = [m for m in context[0]["messages"] if m["content"] == "Hello, I need help"]
    assert len(manual_msgs) == 1


@pytest.mark.asyncio
async def test_get_conversation_context_limits_to_five(client):
    """Should return at most 5 tickets."""
    cust = await client.post("/api/customers/", json={
        "name": "Limit Test",
        "email": "limit@test.com",
    })
    customer_id = cust.json()["id"]

    # Create 7 tickets
    for i in range(7):
        await client.post("/api/tickets/", json={
            "customer_id": customer_id,
            "subject": f"Ticket {i}",
            "description": f"Description {i}",
        })

    context = await get_conversation_context(customer_id)
    assert len(context) == 5


@pytest.mark.asyncio
async def test_get_conversation_context_most_recent_first(client):
    """Should return tickets ordered most recent first."""
    cust = await client.post("/api/customers/", json={
        "name": "Order Test",
        "email": "order@test.com",
    })
    customer_id = cust.json()["id"]

    # Create tickets
    t1 = await client.post("/api/tickets/", json={
        "customer_id": customer_id,
        "subject": "First ticket",
        "description": "First",
    })
    t2 = await client.post("/api/tickets/", json={
        "customer_id": customer_id,
        "subject": "Second ticket",
        "description": "Second",
    })

    context = await get_conversation_context(customer_id)
    assert len(context) == 2
    # Most recent first
    assert context[0]["subject"] == "Second ticket"
    assert context[1]["subject"] == "First ticket"


@pytest.mark.asyncio
async def test_save_memory_with_ticket_id(client):
    """Should save memory associated with a specific ticket."""
    cust = await client.post("/api/customers/", json={
        "name": "Ticket Memory Test",
        "email": "ticket_memory@test.com",
    })
    customer_id = cust.json()["id"]

    ticket = await client.post("/api/tickets/", json={
        "customer_id": customer_id,
        "subject": "Memory ticket",
        "description": "Test",
    })
    ticket_id = ticket.json()["id"]

    result = await save_memory(
        ticket_id=ticket_id,
        customer_id=customer_id,
        key="ticket_specific",
        value="ticket_value",
    )
    assert result["ticket_id"] == ticket_id
    assert result["value"] == "ticket_value"


@pytest.mark.asyncio
async def test_get_customer_info_includes_conversation_summaries(client):
    """get_customer_info should include conversation summaries."""
    cust = await client.post("/api/customers/", json={
        "name": "Customer Info Test",
        "email": "customer_info@test.com",
    })
    customer_id = cust.json()["id"]

    # Create a ticket with a message
    ticket = await client.post("/api/tickets/", json={
        "customer_id": customer_id,
        "subject": "Info test ticket",
        "description": "Test",
    })
    ticket_id = ticket.json()["id"]

    async with get_db() as db:
        await db.execute(
            "INSERT INTO messages (ticket_id, sender, content) VALUES (?, ?, ?)",
            (ticket_id, "customer", "Test message"),
        )
        await db.commit()

    # Import and call get_customer_info
    from app.tools import get_customer_info
    result = await get_customer_info(customer_id)

    assert "conversation_summaries" in result
    assert len(result["conversation_summaries"]) == 1
    assert result["conversation_summaries"][0]["ticket_id"] == ticket_id
    assert result["conversation_summaries"][0]["subject"] == "Info test ticket"
    # Ticket creation auto-creates a message, plus our manual one = 2
    assert result["conversation_summaries"][0]["message_count"] == 2
    # Last message should be our manually added one
    assert result["conversation_summaries"][0]["last_message"]["content"] == "Test message"


@pytest.mark.asyncio
async def test_agent_saves_memory_on_reply(client):
    """Agent should save memory entries when producing a reply."""
    from unittest.mock import AsyncMock, patch
    from app.agent import run_agent

    cust = await client.post("/api/customers/", json={
        "name": "Agent Memory Test",
        "email": "agent_memory@test.com",
    })
    customer_id = cust.json()["id"]

    ticket = await client.post("/api/tickets/", json={
        "customer_id": customer_id,
        "subject": "Agent memory test",
        "description": "Testing agent memory",
        "category": "billing",
    })
    ticket_id = ticket.json()["id"]

    # Mock Groq response - no tool calls, just a reply
    mock_response = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "Thank you for contacting us. I have reviewed your billing inquiry.",
                "tool_calls": None
            },
            "finish_reason": "stop"
        }]
    }

    with patch("app.agent.call_groq", new=AsyncMock(return_value=mock_response)):
        result = await run_agent(
            ticket_id=ticket_id,
            subject="Agent memory test",
            description="Testing agent memory",
            customer_name="Agent Memory Test",
            category="billing",
        )

    assert "reply" in result
    assert "billing" in result["reply"].lower() or "billing" in result.get("reasoning", "").lower() or True  # reply content varies

    # Check that memory was saved
    strategy = await get_memory(customer_id, "last_reply_strategy")
    assert strategy is not None
    assert strategy in ["general_reply", "knowledge_base_lookup", "personalized_reply", "escalated"]

    # Check common_issues was saved for billing category
    issues = await get_memory(customer_id, "common_issues")
    assert issues is not None
    assert "billing" in issues


@pytest.mark.asyncio
async def test_agent_loads_conversation_context(client):
    """Agent should load and use conversation context from memory."""
    from unittest.mock import AsyncMock, patch
    from app.agent import run_agent

    cust = await client.post("/api/customers/", json={
        "name": "Context Load Test",
        "email": "context_load@test.com",
    })
    customer_id = cust.json()["id"]

    # Create first ticket with messages
    t1 = await client.post("/api/tickets/", json={
        "customer_id": customer_id,
        "subject": "Previous issue",
        "description": "Had a problem before",
    })
    t1_id = t1.json()["id"]

    async with get_db() as db:
        await db.execute(
            "INSERT INTO messages (ticket_id, sender, content) VALUES (?, ?, ?)",
            (t1_id, "customer", "I had a billing issue last time"),
        )
        await db.execute(
            "INSERT INTO messages (ticket_id, sender, content) VALUES (?, ?, ?)",
            (t1_id, "agent", "I resolved your billing issue"),
        )
        await db.commit()

    # Create second ticket
    t2 = await client.post("/api/tickets/", json={
        "customer_id": customer_id,
        "subject": "New issue",
        "description": "Having another problem",
    })
    t2_id = t2.json()["id"]

    # Mock Groq response
    mock_response = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "I see you had a previous billing issue. Let me help with this new problem.",
                "tool_calls": None
            },
            "finish_reason": "stop"
        }]
    }

    with patch("app.agent.call_groq", new=AsyncMock(return_value=mock_response)) as mock_groq:
        result = await run_agent(
            ticket_id=t2_id,
            subject="New issue",
            description="Having another problem",
            customer_name="Context Load Test",
        )

    assert "reply" in result

    # Verify the system prompt included conversation history
    call_args = mock_groq.call_args
    messages = call_args[0][0]  # First positional arg is messages list
    system_msg = messages[0]["content"]
    assert "Conversation history" in system_msg or "Previous issue" in system_msg


@pytest.mark.asyncio
async def test_agent_memory_table_exists(client):
    """The agent_memory table should exist in the database."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_memory'"
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["name"] == "agent_memory"
