"""ResolveAI - AI-powered customer support desk."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from .database import init_db
from .routers import tickets, customers, ai_assist, dashboard
from .auth import AuthMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="ResolveAI",
    description="AI-powered customer support desk",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(AuthMiddleware)

# API routes
app.include_router(tickets.router)
app.include_router(customers.router)
app.include_router(ai_assist.router)
app.include_router(dashboard.router)

# Static files
static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    return FileResponse(str(static_dir.parent / "templates" / "index.html"))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ResolveAI"}
