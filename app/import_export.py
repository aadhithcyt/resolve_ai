"""Import/Export functionality for tickets and customers."""
import csv
import io
import json
import logging
from typing import List
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/import-export", tags=["import_export"])


class TicketImportItem(BaseModel):
    customer_email: str
    subject: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., min_length=1)
    priority: str = Field(default="medium")
    category: str = Field(default="general")
    status: str = Field(default="open")


@router.get("/tickets/export")
async def export_tickets(format: str = "json"):
    """Export all tickets in JSON or CSV format."""
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT t.*, c.name as customer_name, c.email as customer_email
               FROM tickets t JOIN customers c ON t.customer_id = c.id
               ORDER BY t.created_at DESC"""
        )
        tickets = [dict(r) for r in await cursor.fetchall()]

    if format == "json":
        return StreamingResponse(
            io.StringIO(json.dumps(tickets, indent=2, default=str)),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=tickets.json"}
        )
    elif format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Subject", "Customer", "Email", "Status", "Priority", "Category", "Created"])
        for t in tickets:
            writer.writerow([
                t.get("id", ""), t.get("subject", ""), t.get("customer_name", ""),
                t.get("customer_email", ""), t.get("status", ""), t.get("priority", ""),
                t.get("category", ""), t.get("created_at", "")
            ])
        output.seek(0)
        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=tickets.csv"}
        )
    else:
        raise HTTPException(status_code=400, detail="Format must be json or csv")


@router.post("/tickets/import")
async def import_tickets(file: UploadFile = File(...)):
    """Import tickets from a JSON file.

    Expected format: JSON array of objects with customer_email, subject, description,
    and optionally priority, category, status.
    """
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="File must be .json")

    content = await file.read()
    try:
        items = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="JSON must be an array of ticket objects")

    imported = 0
    errors = []

    async with get_db() as db:
        for i, item in enumerate(items):
            try:
                # Find or create customer
                email = item.get("customer_email", "")
                if not email:
                    errors.append(f"Item {i}: missing customer_email")
                    continue

                cursor = await db.execute("SELECT id FROM customers WHERE email = ?", (email,))
                customer = await cursor.fetchone()
                if customer:
                    customer_id = customer["id"]
                else:
                    # Create customer
                    name = item.get("customer_name", email.split("@")[0])
                    cursor = await db.execute(
                        "INSERT INTO customers (name, email) VALUES (?, ?)",
                        (name, email),
                    )
                    customer_id = cursor.lastrowid

                # Create ticket
                subject = item.get("subject", "")
                description = item.get("description", "")
                priority = item.get("priority", "medium")
                category = item.get("category", "general")
                status = item.get("status", "open")

                if not subject or not description:
                    errors.append(f"Item {i}: subject and description are required")
                    continue

                # Compute a real SLA deadline from the priority, and write aware
                # UTC timestamps. Imported tickets must behave like normal ones.
                from .routers.tickets import _compute_sla_due_at

                _now = datetime.now(timezone.utc)
                _sla_due = _compute_sla_due_at(priority, _now)
                await db.execute(
                    """INSERT INTO tickets
                       (customer_id, subject, description, priority, category, status,
                        created_at, updated_at, sla_due_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (customer_id, subject, description, priority, category, status,
                     _now.isoformat(), _now.isoformat(), _sla_due.isoformat()),
                )
                imported += 1
            except Exception as e:
                errors.append(f"Item {i}: {str(e)}")

        await db.commit()

    return {
        "imported": imported,
        "errors": errors,
        "total": len(items),
    }


@router.get("/customers/export")
async def export_customers(format: str = "json"):
    """Export all customers in JSON or CSV format."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM customers ORDER BY created_at DESC")
        customers = [dict(r) for r in await cursor.fetchall()]

    if format == "json":
        return StreamingResponse(
            io.StringIO(json.dumps(customers, indent=2, default=str)),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=customers.json"}
        )
    elif format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Name", "Email", "Phone", "Company", "Created"])
        for c in customers:
            writer.writerow([
                c.get("id", ""), c.get("name", ""), c.get("email", ""),
                c.get("phone", ""), c.get("company", ""), c.get("created_at", "")
            ])
        output.seek(0)
        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=customers.csv"}
        )
    else:
        raise HTTPException(status_code=400, detail="Format must be json or csv")


@router.post("/customers/import")
async def import_customers(file: UploadFile = File(...)):
    """Import customers from a JSON file."""
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="File must be .json")

    content = await file.read()
    try:
        items = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="JSON must be an array")

    imported = 0
    errors = []

    async with get_db() as db:
        for i, item in enumerate(items):
            try:
                name = item.get("name", "")
                email = item.get("email", "")
                if not name or not email:
                    errors.append(f"Item {i}: name and email are required")
                    continue

                await db.execute(
                    "INSERT OR IGNORE INTO customers (name, email, phone, company) VALUES (?, ?, ?, ?)",
                    (name, email, item.get("phone"), item.get("company")),
                )
                imported += 1
            except Exception as e:
                errors.append(f"Item {i}: {str(e)}")

        await db.commit()

    return {
        "imported": imported,
        "errors": errors,
        "total": len(items),
    }
