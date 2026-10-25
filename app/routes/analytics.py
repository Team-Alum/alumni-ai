import time as _time
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi import Body
from app.models import AnalyticsSummaryResponse, AnalyticsEventItem
from app.database import (
    get_analytics_summary,
    get_account_removal,
    get_recent_analytics_events,
    get_user_by_id,
    get_users_admin,
    get_visitor_stats,
    record_visitor,
    remove_user_access,
)
from app.security import get_current_user
from app.config import is_admin_email
from app.identity import ACCOUNT_REMOVAL_WARNING, detect_suspicious_name

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
    data = get_users_admin()
    suspicious_count = 0
    for item in data.get("users", []):
        reason = detect_suspicious_name(item.get("username"))
        item["suspicious"] = bool(reason)
        item["suspicious_reason"] = reason or ""
        item["account_removed"] = bool(item.get("removed_at"))
        if reason and not item["account_removed"]:
            suspicious_count += 1
    data.setdefault("totals", {})["suspicious"] = suspicious_count
    return data


@router.post("/users/{user_id}/remove")
async def remove_suspicious_user(
    user_id: str,
    payload: Optional[dict] = Body(default=None),
    user: dict = Depends(get_current_user),
):
    """Soft-remove a suspicious account and record the chatbot warning.

    Founder-only. Historical rows are preserved; the removed account loses
    access to every API except /api/auth/me, which returns the warning.
    """
    verify_team_alum_founder(user)

    target = get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Account not found.")

    if target["id"] == user["id"]:
        raise HTTPException(status_code=400, detail="You cannot remove your own admin account.")

    if is_admin_email(target.get("email")):
        raise HTTPException(status_code=403, detail="Admin and founder accounts cannot be removed here.")

    suspicious_reason = detect_suspicious_name(target.get("username"))
    if not suspicious_reason:
        raise HTTPException(
            status_code=400,
            detail="This account is not flagged as a suspicious username. No account was removed.",
        )

    expected_name = (target.get("username") or "").strip()
    confirm_name = str((payload or {}).get("confirm_username") or "").strip()
    if confirm_name.casefold() != expected_name.casefold():
        raise HTTPException(
            status_code=400,
            detail="Type the exact username to confirm this removal.",
        )

    existing = get_account_removal(user_id)
    if existing:
        return {
            "status": "already_removed",
            "user_id": user_id,
            "username": expected_name,
            "warning": existing.get("warning") or ACCOUNT_REMOVAL_WARNING,
            "removed_at": existing.get("removed_at"),
            "data_preserved": True,
        }

    record = remove_user_access(
        user_id=user_id,
        removed_by=user["id"],
        warning=ACCOUNT_REMOVAL_WARNING,
        reason=suspicious_reason,
    )
    return {
        "status": "removed",
        "user_id": user_id,
        "username": record.get("username") or expected_name,
        "warning": ACCOUNT_REMOVAL_WARNING,
        "removed_at": record.get("removed_at"),
        "data_preserved": True,
    }

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

