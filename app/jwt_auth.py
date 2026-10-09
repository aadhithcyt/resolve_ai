"""JWT authentication for support agents."""
import os
import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from typing import Literal
from .database import get_db

# ─── Config ──────────────────────────────────────────────────────────────────

JWT_SECRET_KEY = os.getenv("RESOLVEAI_JWT_SECRET", "resolveai-jwt-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_HOURS = 24

# ─── Models ──────────────────────────────────────────────────────────────────


class AgentCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=6, max_length=128)
    name: str = Field(..., min_length=1, max_length=200)
    role: Literal["admin", "agent"] = "agent"


class AgentLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AgentResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str
    created_at: str


# ─── Password hashing ────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


# ─── JWT token creation/verification ────────────────────────────────────────


def create_access_token(agent_id: int, email: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(agent_id),
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=JWT_ACCESS_TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─── Dependencies ────────────────────────────────────────────────────────────


async def get_current_agent(request: Request) -> dict:
    """Extract and verify JWT from Authorization header."""
    # If middleware already verified the token, use that
    if hasattr(request.state, "agent"):
        return request.state.agent

    # Otherwise, verify the token ourselves
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth_header[7:]
    payload = decode_access_token(token)
    return {
        "id": int(payload["sub"]),
        "email": payload["email"],
        "role": payload["role"],
    }


async def require_admin(agent: dict = Depends(get_current_agent)) -> dict:
    """Require admin role."""
    if agent["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return agent


# ─── Router ──────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(credentials: AgentLogin):
    """Authenticate agent and return JWT token."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, email, password_hash, name, role FROM agents WHERE email = ?",
            (credentials.email,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        agent = dict(row)
        if not verify_password(credentials.password, agent["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        token = create_access_token(agent["id"], agent["email"], agent["role"])
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=JWT_ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        )


@router.post("/register", response_model=AgentResponse, status_code=201)
async def register(agent_data: AgentCreate, admin: dict = Depends(require_admin)):
    """Register a new agent (admin only)."""
    async with get_db() as db:
        # Check if email already exists
        cursor = await db.execute(
            "SELECT id FROM agents WHERE email = ?", (agent_data.email,)
        )
        if await cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Agent with this email already exists",
            )
        password_hash = hash_password(agent_data.password)
        cursor = await db.execute(
            """INSERT INTO agents (email, password_hash, name, role)
               VALUES (?, ?, ?, ?)""",
            (agent_data.email, password_hash, agent_data.name, agent_data.role),
        )
        await db.commit()
        return AgentResponse(
            id=cursor.lastrowid or 0,
            email=agent_data.email,
            name=agent_data.name,
            role=agent_data.role,
            created_at=datetime.now(timezone.utc).isoformat(),
        )


@router.get("/me", response_model=AgentResponse)
async def get_me(agent: dict = Depends(get_current_agent)):
    """Get current agent info."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, email, name, role, created_at FROM agents WHERE id = ?",
            (agent["id"],),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Agent not found")
        return dict(row)
