"""Tests for customer routes."""
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
async def test_create_customer(client):
    resp = await client.post("/api/customers/", json={
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "+1234567890",
        "company": "Acme Inc",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "John Doe"
    assert data["email"] == "john@example.com"


@pytest.mark.asyncio
async def test_duplicate_email(client):
    await client.post("/api/customers/", json={
        "name": "Jane Doe",
        "email": "jane@example.com",
    })
    resp = await client.post("/api/customers/", json={
        "name": "Jane Smith",
        "email": "jane@example.com",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_customers(client):
    resp = await client.get("/api/customers/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_customer(client):
    created = await client.post("/api/customers/", json={
        "name": "Get Test",
        "email": "get@test.com",
    })
    customer_id = created.json()["id"]

    resp = await client.get(f"/api/customers/{customer_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == customer_id


@pytest.mark.asyncio
async def test_update_customer(client):
    created = await client.post("/api/customers/", json={
        "name": "Update Test",
        "email": "update@test.com",
    })
    customer_id = created.json()["id"]

    resp = await client.put(f"/api/customers/{customer_id}", json={
        "name": "Updated Name",
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_delete_customer(client):
    created = await client.post("/api/customers/", json={
        "name": "Delete Test",
        "email": "delete@test.com",
    })
    customer_id = created.json()["id"]

    resp = await client.delete(f"/api/customers/{customer_id}")
    assert resp.status_code == 204

    resp = await client.get(f"/api/customers/{customer_id}")
    assert resp.status_code == 404
