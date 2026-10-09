"""Tests for SLA tracking."""
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
async def test_ticket_sla_due_at_set(client):
    """Tickets should have sla_due_at set on creation."""
    cust = await client.post("/api/customers/", json={
        "name": "SLA Test",
        "email": "sla@test.com",
    })
    with patch("app.routers.tickets.classify_ticket", new=AsyncMock(return_value={
        "category": "general", "priority": "urgent", "confidence": 1.0, "reasoning": "mock"
    })):
        ticket = await client.post("/api/tickets/", json={
            "customer_id": cust.json()["id"],
            "subject": "SLA test",
            "description": "Testing SLA",
            "priority": "urgent",
        })
    data = ticket.json()
    assert "sla_due_at" in data
    assert data["sla_due_at"] is not None
    # Urgent = 4 hours SLA
    assert data["sla_breached"] is False or data["sla_breached"] == 0


@pytest.mark.asyncio
async def test_ticket_sla_breached_false_for_new(client):
    """New tickets should not be breached."""
    cust = await client.post("/api/customers/", json={
        "name": "SLA Breach Test",
        "email": "sla_breach@test.com",
    })
    with patch("app.routers.tickets.classify_ticket", new=AsyncMock(return_value={
        "category": "general", "priority": "high", "confidence": 1.0, "reasoning": "mock"
    })):
        ticket = await client.post("/api/tickets/", json={
            "customer_id": cust.json()["id"],
            "subject": "SLA breach test",
            "description": "Testing SLA breach",
            "priority": "high",
        })
    data = ticket.json()
    assert data["sla_breached"] is False or data["sla_breached"] == 0


@pytest.mark.asyncio
async def test_ticket_sla_endpoint(client):
    """The SLA endpoint should return SLA details."""
    cust = await client.post("/api/customers/", json={
        "name": "SLA Endpoint Test",
        "email": "sla_endpoint@test.com",
    })
    with patch("app.routers.tickets.classify_ticket", new=AsyncMock(return_value={
        "category": "general", "priority": "medium", "confidence": 1.0, "reasoning": "mock"
    })):
        ticket = await client.post("/api/tickets/", json={
            "customer_id": cust.json()["id"],
            "subject": "SLA endpoint test",
            "description": "Testing SLA endpoint",
            "priority": "medium",
        })
    ticket_id = ticket.json()["id"]

    resp = await client.get(f"/api/tickets/{ticket_id}/sla")
    assert resp.status_code == 200
    data = resp.json()
    assert "sla_due_at" in data
    assert "sla_breached" in data
    assert "status" in data
    assert "priority" in data
    assert "hours_remaining" in data
    assert data["priority"] == "medium"
    assert data["status"] == "open"
    assert data["hours_remaining"] > 0


@pytest.mark.asyncio
async def test_sla_filter_breached(client):
    """Should be able to filter tickets by SLA breach status."""
    # Create a ticket
    cust = await client.post("/api/customers/", json={
        "name": "SLA Filter Test",
        "email": "sla_filter@test.com",
    })
    with patch("app.routers.tickets.classify_ticket", new=AsyncMock(return_value={
        "category": "general", "priority": "low", "confidence": 1.0, "reasoning": "mock"
    })):
        await client.post("/api/tickets/", json={
            "customer_id": cust.json()["id"],
            "subject": "SLA filter test",
            "description": "Testing SLA filter",
            "priority": "low",
        })

    # Filter for breached tickets (should be empty)
    resp = await client.get("/api/tickets/?sla_breached=true")
    assert resp.status_code == 200
    assert len(resp.json()) == 0

    # Filter for non-breached tickets
    resp = await client.get("/api/tickets/?sla_breached=false")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_sla_recomputed_on_priority_change(client):
    """SLA should be recomputed when priority changes."""
    cust = await client.post("/api/customers/", json={
        "name": "SLA Recompute Test",
        "email": "sla_recompute@test.com",
    })
    with patch("app.routers.tickets.classify_ticket", new=AsyncMock(return_value={
        "category": "general", "priority": "low", "confidence": 1.0, "reasoning": "mock"
    })):
        ticket = await client.post("/api/tickets/", json={
            "customer_id": cust.json()["id"],
            "subject": "SLA recompute test",
            "description": "Testing SLA recompute",
            "priority": "low",
        })
    ticket_id = ticket.json()["id"]
    original_sla = ticket.json()["sla_due_at"]

    # Change priority to urgent (4 hour SLA)
    resp = await client.put(f"/api/tickets/{ticket_id}", json={
        "priority": "urgent",
    })
    data = resp.json()
    assert data["priority"] == "urgent"
    # SLA should be different now (sooner)
    assert data["sla_due_at"] != original_sla


@pytest.mark.asyncio
async def test_dashboard_sla_breached_count(client):
    """Dashboard should include SLA breached count."""
    resp = await client.get("/api/dashboard/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "sla_breached" in data
    assert isinstance(data["sla_breached"], int)
    assert data["sla_breached"] >= 0
