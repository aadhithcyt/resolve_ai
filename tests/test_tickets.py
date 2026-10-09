"""Tests for ticket routes."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_create_ticket(client):
    # First create a customer
    cust = await client.post("/api/customers/", json={
        "name": "Test User",
        "email": "test@example.com",
    })
    assert cust.status_code == 201
    customer_id = cust.json()["id"]

    # Mock triage to preserve original priority
    with patch("app.routers.tickets.classify_ticket", new=AsyncMock(return_value={
        "category": "general", "priority": "high", "confidence": 1.0, "reasoning": "mock"
    })):
        # Create ticket
        resp = await client.post("/api/tickets/", json={
            "customer_id": customer_id,
            "subject": "Test ticket",
            "description": "This is a test ticket",
            "priority": "high",
        })
    assert resp.status_code == 201
    data = resp.json()
    assert data["subject"] == "Test ticket"
    assert data["status"] == "open"
    assert data["priority"] == "high"


@pytest.mark.asyncio
async def test_list_tickets(client):
    resp = await client.get("/api/tickets/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_ticket(client):
    # Create customer + ticket
    cust = await client.post("/api/customers/", json={
        "name": "Test User 2",
        "email": "test2@example.com",
    })
    ticket = await client.post("/api/tickets/", json={
        "customer_id": cust.json()["id"],
        "subject": "Another ticket",
        "description": "Description here",
    })
    ticket_id = ticket.json()["id"]

    resp = await client.get(f"/api/tickets/{ticket_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == ticket_id


@pytest.mark.asyncio
async def test_update_ticket(client):
    cust = await client.post("/api/customers/", json={
        "name": "Test User 3",
        "email": "test3@example.com",
    })
    ticket = await client.post("/api/tickets/", json={
        "customer_id": cust.json()["id"],
        "subject": "Update me",
        "description": "Update description",
    })
    ticket_id = ticket.json()["id"]

    resp = await client.put(f"/api/tickets/{ticket_id}", json={
        "status": "in_progress",
        "priority": "urgent",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "in_progress"
    assert data["priority"] == "urgent"


@pytest.mark.asyncio
async def test_delete_ticket(client):
    cust = await client.post("/api/customers/", json={
        "name": "Test User 4",
        "email": "test4@example.com",
    })
    ticket = await client.post("/api/tickets/", json={
        "customer_id": cust.json()["id"],
        "subject": "Delete me",
        "description": "Delete description",
    })
    ticket_id = ticket.json()["id"]

    resp = await client.delete(f"/api/tickets/{ticket_id}")
    assert resp.status_code == 204

    resp = await client.get(f"/api/tickets/{ticket_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_ticket_messages(client):
    cust = await client.post("/api/customers/", json={
        "name": "Test User 5",
        "email": "test5@example.com",
    })
    ticket = await client.post("/api/tickets/", json={
        "customer_id": cust.json()["id"],
        "subject": "Message test",
        "description": "Initial message",
    })
    ticket_id = ticket.json()["id"]

    # Add a reply
    resp = await client.post(f"/api/tickets/{ticket_id}/messages", json={
        "sender": "agent",
        "content": "Thanks for reaching out!",
    })
    assert resp.status_code == 201

    # Get messages
    resp = await client.get(f"/api/tickets/{ticket_id}/messages")
    assert resp.status_code == 200
    messages = resp.json()
    assert len(messages) >= 2  # initial + reply
