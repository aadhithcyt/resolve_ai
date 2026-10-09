"""ResolveAI - AI-powered customer support desk."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from .database import init_db
from .workers import start_workers, stop_workers
from .routers import tickets, customers, ai_assist, dashboard
from .agent_router import router as agent_router
from .routers.kb import router as kb_router
from .sse import router as sse_router
from .analytics_router import router as analytics_router
from .auth import AuthMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    workers = await start_workers()
    yield
    await stop_workers()


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
app.include_router(agent_router)
app.include_router(kb_router)
app.include_router(sse_router)
app.include_router(analytics_router)

# Static files
static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    return FileResponse(str(static_dir.parent / "templates" / "index.html"))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ResolveAI"}
