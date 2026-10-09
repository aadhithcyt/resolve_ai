"""Tests for knowledge base routes."""
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
async def test_create_kb_article(client):
    resp = await client.post("/api/kb/", json={
        "title": "Test Article",
        "content": "This is test content for the knowledge base.",
        "category": "testing",
        "tags": "test,kb",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Test Article"
    assert data["content"] == "This is test content for the knowledge base."
    assert data["category"] == "testing"
    assert data["tags"] == "test,kb"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_kb_article_minimal(client):
    """Create with only required fields."""
    resp = await client.post("/api/kb/", json={
        "title": "Minimal Article",
        "content": "Minimal content",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["category"] == "general"
    assert data["tags"] is None


@pytest.mark.asyncio
async def test_create_kb_article_validation_error(client):
    """Empty title should fail validation."""
    resp = await client.post("/api/kb/", json={
        "title": "",
        "content": "Some content",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_kb_articles(client):
    # Create a few articles
    for i in range(3):
        await client.post("/api/kb/", json={
            "title": f"List Test {i}",
            "content": f"Content for list test {i}",
            "category": "testing",
        })

    resp = await client.get("/api/kb/")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 3  # At least our 3 (plus any seeded)


@pytest.mark.asyncio
async def test_list_kb_articles_with_category_filter(client):
    await client.post("/api/kb/", json={
        "title": "Filtered Article",
        "content": "Content for filtered category",
        "category": "unique_cat",
    })

    resp = await client.get("/api/kb/", params={"category": "unique_cat"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(a["category"] == "unique_cat" for a in data)


@pytest.mark.asyncio
async def test_list_kb_articles_pagination(client):
    resp = await client.get("/api/kb/", params={"skip": 0, "limit": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) <= 2


@pytest.mark.asyncio
async def test_get_kb_article(client):
    create_resp = await client.post("/api/kb/", json={
        "title": "Get Test",
        "content": "Content to retrieve",
    })
    article_id = create_resp.json()["id"]

    resp = await client.get(f"/api/kb/{article_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == article_id
    assert data["title"] == "Get Test"


@pytest.mark.asyncio
async def test_get_kb_article_not_found(client):
    resp = await client.get("/api/kb/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_kb_article(client):
    create_resp = await client.post("/api/kb/", json={
        "title": "Delete Test",
        "content": "Content to delete",
    })
    article_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/kb/{article_id}")
    assert resp.status_code == 204

    # Verify it's gone
    resp = await client.get(f"/api/kb/{article_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_kb_article_not_found(client):
    resp = await client.delete("/api/kb/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_search_kb_fts(client):
    """FTS5 search should find articles by content."""
    await client.post("/api/kb/", json={
        "title": "Password Reset Guide",
        "content": "To reset your password, click the forgot password link on the login page.",
        "category": "account",
    })

    resp = await client.get("/api/kb/search", params={"query": "password"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "password"
    assert data["total"] >= 1
    assert len(data["results"]) >= 1
    # Check that at least one result contains "password"
    found = any("password" in r["content"].lower() or "password" in r["title"].lower()
                for r in data["results"])
    assert found


@pytest.mark.asyncio
async def test_search_kb_fts_title_match(client):
    """FTS5 search should match on title."""
    await client.post("/api/kb/", json={
        "title": "UniqueXYZKeyword Guide",
        "content": "Some generic content here.",
    })

    resp = await client.get("/api/kb/search", params={"query": "UniqueXYZKeyword"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_search_kb_empty_results(client):
    """Search with no matches should return empty results."""
    resp = await client.get("/api/kb/search", params={"query": "zzznonexistentkeyword999"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "zzznonexistentkeyword999"
    assert data["total"] == 0
    assert data["results"] == []


@pytest.mark.asyncio
async def test_search_kb_like_fallback(client):
    """Search with special FTS5 syntax that triggers LIKE fallback."""
    await client.post("/api/kb/", json={
        "title": "Fallback Test Article",
        "content": "This article tests the LIKE fallback mechanism for searches.",
    })

    # FTS5 special characters like quotes can cause syntax errors,
    # triggering the LIKE fallback
    resp = await client.get("/api/kb/search", params={"query": '"unclosed quote'})
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == '"unclosed quote'
    # LIKE fallback should still work (may or may not match)
    assert isinstance(data["results"], list)
    assert isinstance(data["total"], int)


@pytest.mark.asyncio
async def test_search_kb_limit(client):
    """Search should respect the limit parameter."""
    # Create multiple articles with same keyword
    for i in range(5):
        await client.post("/api/kb/", json={
            "title": f"Limit Test {i}",
            "content": "limitsearchterm in content",
        })

    resp = await client.get("/api/kb/search", params={"query": "limitsearchterm", "limit": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) <= 2


@pytest.mark.asyncio
async def test_seeded_articles_exist(client):
    """Verify that seed articles are present on startup."""
    resp = await client.get("/api/kb/")
    assert resp.status_code == 200
    data = resp.json()
    # Should have at least the 8 seeded articles
    assert len(data) >= 8
    # Check for known seed article titles
    titles = [a["title"] for a in data]
    assert "How to Reset Your Password" in titles
    assert "Billing and Subscription FAQ" in titles
    assert "API Rate Limits and Best Practices" in titles


@pytest.mark.asyncio
async def test_seeded_articles_searchable(client):
    """Seeded articles should be searchable via FTS5."""
    resp = await client.get("/api/kb/search", params={"query": "billing"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    titles = [r["title"] for r in data["results"]]
    assert "Billing and Subscription FAQ" in titles


@pytest.mark.asyncio
async def test_delete_removes_from_fts(client):
    """Deleting an article should also remove it from FTS index."""
    create_resp = await client.post("/api/kb/", json={
        "title": "DeleteFTSTest UniqueToken",
        "content": "This article will be deleted and should not appear in search.",
    })
    article_id = create_resp.json()["id"]

    # Verify it's searchable
    resp = await client.get("/api/kb/search", params={"query": "UniqueToken"})
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # Delete it
    await client.delete(f"/api/kb/{article_id}")

    # Verify it's no longer searchable
    resp = await client.get("/api/kb/search", params={"query": "UniqueToken"})
    assert resp.status_code == 200
    data = resp.json()
    titles = [r["title"] for r in data["results"]]
    assert "DeleteFTSTest UniqueToken" not in titles
