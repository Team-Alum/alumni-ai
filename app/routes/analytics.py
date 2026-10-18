from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from app.models import AnalyticsSummaryResponse, AnalyticsEventItem
from app.database import get_analytics_summary, get_recent_analytics_events
from app.security import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["Analytics & Usage Analysis"])

def verify_team_alum_founder(user: dict):
    if not bool(user.get("is_team_alum", 0)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted. System analytics and telemetry are reserved exclusively for Team Alum administrators."
        )

@router.get("/overview", response_model=AnalyticsSummaryResponse)
async def get_overview(user: dict = Depends(get_current_user)):
    """
    Returns aggregated metrics, user traffic, provider distribution,
    latency, and mode breakdown. Reserved exclusively for Team Alum founders.
    """
    verify_team_alum_founder(user)
    summary = get_analytics_summary()
    return summary

@router.get("/events", response_model=List[AnalyticsEventItem])
async def get_events(
    limit: int = Query(default=50, ge=1, le=500),
    user: dict = Depends(get_current_user)
):
    """
    Returns detailed recent query events including provider used,
    latency, prompt length, and operational mode. Reserved exclusively for Team Alum founders.
    """
    verify_team_alum_founder(user)
    events = get_recent_analytics_events(limit=limit)
    return events

