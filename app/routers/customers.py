"""Customer management routes."""
from fastapi import APIRouter, HTTPException
from typing import List
from ..database import get_db
from ..models import CustomerCreate, CustomerUpdate, CustomerResponse

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.post("/", response_model=CustomerResponse, status_code=201)
async def create_customer(customer: CustomerCreate):
    async with get_db() as db:
        try:
            cursor = await db.execute(
                "INSERT INTO customers (name, email, phone, company) VALUES (?, ?, ?, ?)",
                (customer.name, customer.email, customer.phone, customer.company),
            )
            await db.commit()
            row = await db.execute(
                "SELECT * FROM customers WHERE id = ?", (cursor.lastrowid,)
            )
            return dict(await row.fetchone())
        except Exception as e:
            if "UNIQUE" in str(e):
                raise HTTPException(status_code=409, detail="Email already exists")
            raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[CustomerResponse])
async def list_customers(skip: int = 0, limit: int = 100):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM customers ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, skip),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(customer_id: int):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM customers WHERE id = ?", (customer_id,)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Customer not found")
        return dict(row)


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(customer_id: int, customer: CustomerUpdate):
    async with get_db() as db:
        existing = await db.execute(
            "SELECT * FROM customers WHERE id = ?", (customer_id,)
        )
        if not await existing.fetchone():
            raise HTTPException(status_code=404, detail="Customer not found")

        fields = []
        values = []
        for field, value in customer.model_dump(exclude_unset=True).items():
            if value is not None:
                fields.append(f"{field} = ?")
                values.append(value)

        if fields:
            values.append(customer_id)
            await db.execute(
                f"UPDATE customers SET {', '.join(fields)} WHERE id = ?", values
            )
            await db.commit()

        cursor = await db.execute(
            "SELECT * FROM customers WHERE id = ?", (customer_id,)
        )
        return dict(await cursor.fetchone())


@router.delete("/{customer_id}", status_code=204)
async def delete_customer(customer_id: int):
    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM customers WHERE id = ?", (customer_id,)
        )
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Customer not found")
