"""Analytics router for AI performance metrics."""
from fastapi import APIRouter
from .analytics import get_ai_analytics

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/ai")
async def get_ai_metrics():
    """Get AI performance analytics."""
    return await get_ai_analytics()
