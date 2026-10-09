"""ResolveAI - AI-powered customer support desk."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
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
from .jwt_auth import router as auth_router
from .portal import router as portal_router
from .webhook import router as webhook_router
from .import_export import router as import_export_router
from .routers.sla_report import router as sla_report_router
from .team import router as team_router
from .attachments import router as attachments_router
from .notifications import router as notifications_router
from .presence import router as presence_router
from .chat import router as chat_router
from app.sse import ticket_events


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


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# API routes
app.include_router(tickets.router)
app.include_router(customers.router)
app.include_router(ai_assist.router)
app.include_router(dashboard.router)
app.include_router(agent_router)
app.include_router(kb_router)
app.include_router(sse_router)
app.include_router(analytics_router)
app.include_router(auth_router)
app.include_router(portal_router)
app.include_router(webhook_router)
app.include_router(import_export_router)
app.include_router(attachments_router)
app.include_router(notifications_router)
app.include_router(presence_router)
app.include_router(chat_router)
app.include_router(sla_report_router)
app.include_router(team_router)

# Static files
static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Public files (service worker, etc.)
public_dir = Path(__file__).resolve().parent.parent / "public"
if public_dir.exists():
    app.mount("/public", StaticFiles(directory=str(public_dir)), name="public")


@app.get("/")
async def root():
    return FileResponse(str(static_dir.parent / "templates" / "index.html"))


@app.get("/sw.js")
async def service_worker():
    """Serve the service worker from the root scope."""
    public_dir = Path(__file__).resolve().parent.parent / "public"
    sw_path = public_dir / "sw.js"
    if sw_path.exists():
        return FileResponse(str(sw_path), media_type="application/javascript")
    raise HTTPException(status_code=404, detail="Service worker not found")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ResolveAI"}


# SSE endpoint registered directly so it appears in app.routes with a .path attribute
@app.get("/api/events/tickets")
async def sse_ticket_events():
    return ticket_events()
