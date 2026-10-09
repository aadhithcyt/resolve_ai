"""Attachment upload, listing, download, and deletion routes."""
import os
import uuid
import logging
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

from .config import UPLOADS_DIR
from .database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["attachments"])

# Maximum upload size: 10 MB
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".txt", ".log", ".csv", ".json", ".zip"}


def _ensure_uploads_dir() -> Path:
    """Create uploads directory if it doesn't exist."""
    path = Path(UPLOADS_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


@router.post("/tickets/{ticket_id}/attachments", status_code=201)
async def upload_attachment(ticket_id: int, file: UploadFile = File(...)):
    """Upload a file attachment to a ticket."""
    # Verify ticket exists
    async with get_db() as db:
        cursor = await db.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Ticket not found")

    # Validate file extension
    file_ext = Path(file.filename or "").suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type not allowed: {file_ext}")

    # Read and validate file
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")

    # Save to disk
    uploads_dir = _ensure_uploads_dir()
    safe_name = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = uploads_dir / safe_name
    with open(file_path, "wb") as f:
        f.write(content)

    # Store in database
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO attachments (ticket_id, filename, content_type, file_path, uploaded_by)
               VALUES (?, ?, ?, ?, ?)""",
            (ticket_id, file.filename, file.content_type, str(file_path), "agent"),
        )
        await db.commit()
        attachment_id = cursor.lastrowid

        row = await db.execute("SELECT * FROM attachments WHERE id = ?", (attachment_id,))
        return dict(await row.fetchone())


@router.get("/tickets/{ticket_id}/attachments")
async def list_attachments(ticket_id: int):
    """List all attachments for a ticket."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM attachments WHERE ticket_id = ? ORDER BY uploaded_at DESC",
            (ticket_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


@router.get("/attachments/{attachment_id}/download")
async def download_attachment(attachment_id: int):
    """Download an attachment file."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM attachments WHERE id = ?", (attachment_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Attachment not found")
        data = dict(row)

    file_path = Path(data["file_path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=str(file_path),
        filename=data["filename"],
        media_type=data["content_type"] or "application/octet-stream",
    )


@router.delete("/attachments/{attachment_id}", status_code=204)
async def delete_attachment(attachment_id: int):
    """Delete an attachment and its file from disk."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM attachments WHERE id = ?", (attachment_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Attachment not found")
        data = dict(row)

        await db.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
        await db.commit()

    # Remove file from disk
    file_path = Path(data["file_path"])
    if file_path.exists():
        file_path.unlink()
