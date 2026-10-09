"""Knowledge base router for RAG-lite search."""
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel, Field
from ..database import get_db

router = APIRouter(prefix="/api/kb", tags=["knowledge_base"])


class KBCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    content: str = Field(..., min_length=1)
    category: str = Field(default="general", max_length=100)
    tags: Optional[str] = Field(None, max_length=200)


class KBResponse(BaseModel):
    id: int
    title: str
    content: str
    category: str
    tags: Optional[str] = None
    created_at: str


class KBSearchResult(BaseModel):
    results: List[KBResponse]
    query: str
    total: int


@router.post("/", response_model=KBResponse, status_code=201)
async def create_kb_article(article: KBCreate):
    """Add a knowledge base article."""
    async with get_db() as db:
        cursor = await db.execute(
            "INSERT INTO knowledge_base (title, content, category, tags) VALUES (?, ?, ?, ?)",
            (article.title, article.content, article.category, article.tags),
        )
        await db.commit()

        # Update FTS index
        await db.execute(
            "INSERT INTO knowledge_base_fts(rowid, title, content) VALUES (?, ?, ?)",
            (cursor.lastrowid, article.title, article.content),
        )
        await db.commit()

        row = await db.execute("SELECT * FROM knowledge_base WHERE id = ?", (cursor.lastrowid,))
        return dict(await row.fetchone())


@router.get("/", response_model=List[KBResponse])
async def list_kb_articles(
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
):
    """List knowledge base articles."""
    async with get_db() as db:
        if category:
            cursor = await db.execute(
                "SELECT * FROM knowledge_base WHERE category = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (category, limit, skip),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM knowledge_base ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, skip),
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


@router.get("/search", response_model=KBSearchResult)
async def search_kb(query: str, limit: int = 5):
    """Search the knowledge base using FTS5."""
    async with get_db() as db:
        try:
            cursor = await db.execute(
                """SELECT kb.* FROM knowledge_base kb
                   JOIN knowledge_base_fts fts ON kb.id = fts.rowid
                   WHERE knowledge_base_fts MATCH ?
                   ORDER BY rank LIMIT ?""",
                (query, limit),
            )
        except Exception:
            # Fallback to LIKE
            cursor = await db.execute(
                "SELECT * FROM knowledge_base WHERE content LIKE ? OR title LIKE ? LIMIT ?",
                (f"%{query}%", f"%{query}%", limit),
            )

        rows = await cursor.fetchall()
        results = [dict(r) for r in rows]
        return KBSearchResult(results=results, query=query, total=len(results))


@router.get("/{article_id}", response_model=KBResponse)
async def get_kb_article(article_id: int):
    """Get a specific knowledge base article."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM knowledge_base WHERE id = ?", (article_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Article not found")
        return dict(row)


@router.delete("/{article_id}", status_code=204)
async def delete_kb_article(article_id: int):
    """Delete a knowledge base article."""
    async with get_db() as db:
        cursor = await db.execute("DELETE FROM knowledge_base WHERE id = ?", (article_id,))
        await db.execute("DELETE FROM knowledge_base_fts WHERE rowid = ?", (article_id,))
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Article not found")
