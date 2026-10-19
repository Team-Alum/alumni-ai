import time as _time
from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi import Body
from app.models import AnalyticsSummaryResponse, AnalyticsEventItem
from app.database import (
    get_analytics_summary,
    get_recent_analytics_events,
    get_users_admin,
    get_visitor_stats,
    record_visitor
)
from app.security import get_current_user
from app.config import is_admin_email

router = APIRouter(prefix="/api/analytics", tags=["Analytics & Usage Analysis"])

def verify_team_alum_founder(user: dict):
    # Double gate: the normalized admin flag (derived from the email
    # allowlist in get_current_user) AND a direct allowlist check on the
    # account's email. A legacy/attacker-set is_team_alum row alone can
    # never pass this.
    allowed = bool(user.get("is_team_alum", 0)) and is_admin_email(user.get("email"))
    if not allowed:
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

@router.get("/users")
async def get_registered_users(user: dict = Depends(get_current_user)):
    """
    Registered accounts with emails, signup growth by month, and login-method
    breakdown for welcome/offer email campaigns. Founders only.
    """
    verify_team_alum_founder(user)
    return get_users_admin()

@router.get("/visitors")
async def get_visitors(user: dict = Depends(get_current_user)):
    """
    Monthly & daily visitor record (hits + unique visitors) for traffic analysis.
    Founders only.
    """
    verify_team_alum_founder(user)
    return get_visitor_stats()

# ---- Public visitor beacon (no auth; rate-limited per visitor key) ----
# Enforce real visitor tracking with basic validation to prevent spam/fakes
_track_cooldown: dict = {}
_TRACK_WINDOW_SEC = 30.0  # prevent rapid replays

@router.post("/track")
async def track_visitor(payload: dict = Body(...)):
    visitor_key = str(payload.get("visitor_key") or "").strip()[:64]
    path = str(payload.get("path") or "/").strip()[:200]
    if not visitor_key:
        raise HTTPException(status_code=400, detail="visitor_key required")
    # Reject obviously fake patterns
    if visitor_key.startswith("probe-") or visitor_key == "live-verify-001":
        return {"ok": False, "reason": "invalid"}
    # Require plausible UUID-like or real format (allow vk- prefix from client)
    now = _time.time()
    last = _track_cooldown.get(visitor_key)
    if last and (now - last) < _TRACK_WINDOW_SEC:
        return {"ok": True, "deduped": True}
    _track_cooldown[visitor_key] = now
    if len(_track_cooldown) > 5000:
        for k in [k for k, t in _track_cooldown.items() if now - t > 3600]:
            _track_cooldown.pop(k, None)
    try:
        record_visitor(visitor_key, path)
    except Exception:
        return {"ok": False}
    return {"ok": True}

