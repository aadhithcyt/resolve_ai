"""Tests for AI routes."""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_ai_reply(client):
    # Create customer + ticket
    cust = await client.post("/api/customers/", json={
        "name": "AI Test",
        "email": "ai@test.com",
    })
    ticket = await client.post("/api/tickets/", json={
        "customer_id": cust.json()["id"],
        "subject": "AI reply test",
        "description": "I need help with my account",
    })
    ticket_id = ticket.json()["id"]

    resp = await client.post("/api/ai/reply", json={
        "ticket_id": ticket_id,
        "tone": "professional",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data
    assert "sentiment" in data
    assert "confidence" in data


@pytest.mark.asyncio
async def test_sentiment_analysis(client):
    cust = await client.post("/api/customers/", json={
        "name": "Sentiment Test",
        "email": "sentiment@test.com",
    })
    ticket = await client.post("/api/tickets/", json={
        "customer_id": cust.json()["id"],
        "subject": "Sentiment test",
        "description": "I am very frustrated with this service!",
    })
    ticket_id = ticket.json()["id"]

    resp = await client.post(f"/api/ai/sentiment/{ticket_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "sentiment" in data
    assert "confidence" in data
