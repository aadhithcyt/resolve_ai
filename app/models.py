"""Pydantic models for request/response validation."""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: str = Field(..., min_length=3, max_length=200)
    phone: Optional[str] = Field(None, max_length=50)
    company: Optional[str] = Field(None, max_length=200)


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    email: Optional[str] = Field(None, min_length=3, max_length=200)
    phone: Optional[str] = Field(None, max_length=50)
    company: Optional[str] = Field(None, max_length=200)


class CustomerResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str] = None
    company: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class TicketCreate(BaseModel):
    customer_id: int
    subject: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., min_length=1)
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    category: str = Field(default="general", max_length=100)


class TicketUpdate(BaseModel):
    subject: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = Field(None, min_length=1)
    status: Optional[Literal["open", "in_progress", "resolved", "closed"]] = None
    priority: Optional[Literal["low", "medium", "high", "urgent"]] = None
    category: Optional[str] = Field(None, max_length=100)
    assigned_to: Optional[str] = Field(None, max_length=100)


class TicketResponse(BaseModel):
    id: int
    customer_id: int
    subject: str
    description: str
    status: str
    priority: str
    category: str
    sentiment: Optional[str] = None
    ai_reply: Optional[str] = None
    assigned_to: Optional[str] = None
    created_at: str
    updated_at: str
    resolved_at: Optional[str] = None

    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    sender: Literal["customer", "agent", "system"]
    content: str = Field(..., min_length=1)
    is_ai_generated: bool = False


class MessageResponse(BaseModel):
    id: int
    ticket_id: int
    sender: str
    content: str
    is_ai_generated: bool
    created_at: str

    class Config:
        from_attributes = True


class AIReplyRequest(BaseModel):
    ticket_id: int
    tone: Literal["professional", "friendly", "empathetic", "concise"] = "professional"


class AIReplyResponse(BaseModel):
    reply: str
    sentiment: str
    confidence: float


class DashboardStats(BaseModel):
    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    resolved_tickets: int
    closed_tickets: int
    avg_resolution_hours: Optional[float]
    tickets_by_priority: dict
    tickets_by_category: dict
    recent_tickets: list
