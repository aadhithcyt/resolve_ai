"""Tests for attachment routes."""
import pytest
import pytest_asyncio
import os
import tempfile
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def sample_ticket(client):
    """Create a customer and ticket for attachment tests."""
    cust = await client.post("/api/customers/", json={
        "name": "Attachment Test",
        "email": "attach@test.com",
    })
    ticket = await client.post("/api/tickets/", json={
        "customer_id": cust.json()["id"],
        "subject": "Attachment test ticket",
        "description": "Testing attachments",
    })
    return ticket.json()


@pytest.mark.asyncio
async def test_upload_attachment(client, sample_ticket):
    """Upload a file to a ticket."""
    ticket_id = sample_ticket["id"]
    file_content = b"test file content for attachment"
    files = {"file": ("test.txt", file_content, "text/plain")}
    resp = await client.post(f"/api/tickets/{ticket_id}/attachments", files=files)
    assert resp.status_code == 201
    data = resp.json()
    assert data["ticket_id"] == ticket_id
    assert data["filename"] == "test.txt"
    assert data["content_type"] == "text/plain"
    assert "id" in data
    assert "uploaded_at" in data


@pytest.mark.asyncio
async def test_list_attachments(client, sample_ticket):
    """List attachments for a ticket."""
    ticket_id = sample_ticket["id"]

    # Upload two files
    files1 = {"file": ("file1.txt", b"content1", "text/plain")}
    files2 = {"file": ("file2.txt", b"content2", "text/plain")}
    await client.post(f"/api/tickets/{ticket_id}/attachments", files=files1)
    await client.post(f"/api/tickets/{ticket_id}/attachments", files=files2)

    resp = await client.get(f"/api/tickets/{ticket_id}/attachments")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    filenames = [a["filename"] for a in data]
    assert "file1.txt" in filenames
    assert "file2.txt" in filenames


@pytest.mark.asyncio
async def test_download_attachment(client, sample_ticket):
    """Download an uploaded attachment."""
    ticket_id = sample_ticket["id"]
    file_content = b"download test content"
    files = {"file": ("download.txt", file_content, "text/plain")}
    upload_resp = await client.post(f"/api/tickets/{ticket_id}/attachments", files=files)
    attachment_id = upload_resp.json()["id"]

    resp = await client.get(f"/api/attachments/{attachment_id}/download")
    assert resp.status_code == 200
    assert resp.content == file_content


@pytest.mark.asyncio
async def test_delete_attachment(client, sample_ticket):
    """Delete an attachment."""
    ticket_id = sample_ticket["id"]
    files = {"file": ("delete.txt", b"delete me", "text/plain")}
    upload_resp = await client.post(f"/api/tickets/{ticket_id}/attachments", files=files)
    attachment_id = upload_resp.json()["id"]

    resp = await client.delete(f"/api/attachments/{attachment_id}")
    assert resp.status_code == 204

    # Verify it's gone from the list
    list_resp = await client.get(f"/api/tickets/{ticket_id}/attachments")
    assert len(list_resp.json()) == 0


@pytest.mark.asyncio
async def test_upload_attachment_ticket_not_found(client):
    """Upload to non-existent ticket should return 404."""
    files = {"file": ("test.txt", b"content", "text/plain")}
    resp = await client.post("/api/tickets/99999/attachments", files=files)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_download_attachment_not_found(client):
    """Download non-existent attachment should return 404."""
    resp = await client.get("/api/attachments/99999/download")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_attachment_not_found(client):
    """Delete non-existent attachment should return 404."""
    resp = await client.delete("/api/attachments/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_attachments_empty(client, sample_ticket):
    """List attachments for ticket with no attachments."""
    resp = await client.get(f"/api/tickets/{sample_ticket['id']}/attachments")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_ticket_info_includes_attachments(client, sample_ticket):
    """get_ticket_info tool should include attachments list."""
    from app.tools import get_ticket_info

    ticket_id = sample_ticket["id"]
    files = {"file": ("tool_test.txt", b"tool content", "text/plain")}
    await client.post(f"/api/tickets/{ticket_id}/attachments", files=files)

    result = await get_ticket_info(ticket_id)
    assert "attachments" in result
    assert isinstance(result["attachments"], list)
    assert len(result["attachments"]) == 1
    assert result["attachments"][0]["filename"] == "tool_test.txt"


@pytest.mark.asyncio
async def test_upload_creates_file_on_disk(client, sample_ticket):
    """Uploaded file should be stored on disk."""
    ticket_id = sample_ticket["id"]
    files = {"file": ("disk_test.txt", b"disk content", "text/plain")}
    upload_resp = await client.post(f"/api/tickets/{ticket_id}/attachments", files=files)
    data = upload_resp.json()

    # Check file exists on disk
    file_path = data["file_path"]
    assert os.path.exists(file_path)
    with open(file_path, "rb") as f:
        assert f.read() == b"disk content"


@pytest.mark.asyncio
async def test_delete_removes_file_from_disk(client, sample_ticket):
    """Deleting an attachment should remove the file from disk."""
    ticket_id = sample_ticket["id"]
    files = {"file": ("remove_me.txt", b"remove", "text/plain")}
    upload_resp = await client.post(f"/api/tickets/{ticket_id}/attachments", files=files)
    data = upload_resp.json()
    file_path = data["file_path"]

    assert os.path.exists(file_path)

    await client.delete(f"/api/attachments/{data['id']}")
    assert not os.path.exists(file_path)
