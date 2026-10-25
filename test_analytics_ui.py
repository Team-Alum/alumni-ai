import asyncio
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.services.voice_service import process_voice_query
from app.database import init_db, save_user

init_db()
client = TestClient(app)


def _get_admin_token() -> str:
    """Seed the allowlisted founder locally, then exercise password login.

    Production founder accounts are Google-only. The test suite uses a local
    throwaway database, so seeding one allowlisted row here is safe and keeps
    the analytics access-control path realistic.
    """
    founder_email = "sudarshan.deve@gmail.com"
    save_user(
        user_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, founder_email)),
        username="Sudarshan Hadmode",
        email=founder_email,
        login_method="alum",
        is_team_alum=True,
        password="superSafePassword123",
    )
    login_res = client.post("/api/auth/login", json={
        "username": "Sudarshan Hadmode",
        "email": founder_email,
        "password": "superSafePassword123",
        "login_method": "alum",
        "is_team_alum": True
    })
    assert login_res.status_code == 200, login_res.text
    return login_res.json()["token"]


def test_analytics_and_ui():
    print("=" * 60)
    print("RUNNING ANALYTICS SUITE & UI VERIFICATION")
    print("=" * 60)

    # 1. Acquire an admin session token
    token = _get_admin_token()
    headers = {"Authorization": f"Bearer {token}"}
    print("[PASS] 1. Auth token acquired")

    # 2. Test /api/analytics/overview
    overview_res = client.get("/api/analytics/overview", headers=headers)
    assert overview_res.status_code == 200, f"Overview endpoint failed: {overview_res.text}"
    data = overview_res.json()
    assert "total_users" in data
    assert "total_sessions" in data
    assert "total_queries" in data
    assert "avg_latency_ms" in data
    assert "provider_distribution" in data
    assert "mode_distribution" in data
    assert "status_distribution" in data
    assert "daily_volume" in data
    assert isinstance(data["queries_today"], int), "queries_today missing from live overview"
    assert isinstance(data["active_users_7d"], int), "active_users_7d missing from live overview"
    print(f"[PASS] 2. /api/analytics/overview active: {data['total_users']} users, {data['total_queries']} queries, "
          f"{data['total_sessions']} sessions, {data['queries_today']} today, {data['active_users_7d']} active (7d)")

    # 3. Test /api/analytics/events
    events_res = client.get("/api/analytics/events?limit=10", headers=headers)
    assert events_res.status_code == 200, f"Events endpoint failed: {events_res.text}"
    events = events_res.json()
    assert isinstance(events, list)
    print(f"[PASS] 3. /api/analytics/events active: {len(events)} recent events retrieved")

    # 3b. Users & visitors tabs (must never hang on 'Loading...')
    users_res = client.get("/api/analytics/users", headers=headers)
    assert users_res.status_code == 200, f"Users endpoint failed: {users_res.text}"
    visitors_res = client.get("/api/analytics/visitors", headers=headers)
    assert visitors_res.status_code == 200, f"Visitors endpoint failed: {visitors_res.text}"
    assert "users" in users_res.json() and "monthly" in visitors_res.json()
    print(f"[PASS] 3b. /api/analytics/users + /api/analytics/visitors active")

    # 4. Verify Frontend UI Elements in static/index.html
    home_res = client.get("/")
    assert home_res.status_code == 200
    html = home_res.text
    assert 'id="analytics-modal"' in html, "Missing #analytics-modal in index.html"
    assert 'openAnalyticsModal()' in html, "Missing openAnalyticsModal() in index.html"
    assert 'refreshAnalyticsData()' in html, "Missing refreshAnalyticsData() in index.html"
    assert 'id="analytics-providers-list"' in html, "Missing #analytics-providers-list"
    assert 'id="analytics-modes-list"' in html, "Missing #analytics-modes-list"
    assert 'id="analytics-events-table-body"' in html, "Missing #analytics-events-table-body"
    assert 'exportAnalyticsSnapshot()' in html, "Missing exportAnalyticsSnapshot() in index.html"
    # Live-data blocks (replaced the old hardcoded 'Engine Uptime & Integrity' fake panel)
    assert 'id="analytics-daily-chart"' in html, "Missing #analytics-daily-chart"
    assert 'id="analytics-success-rate"' in html, "Missing #analytics-success-rate"
    assert 'id="analytics-last-updated"' in html, "Missing #analytics-last-updated"
    assert "Engine Uptime &amp; Integrity" not in html and "Engine Uptime & Integrity" not in html, \
        "Fake engine-uptime panel is still present in the overview"
    # Regression guard: analytics renderers must call the real escapeHTML() helper
    assert "escapeHtml(" not in html, "Found undefined escapeHtml( calls — breaks every analytics tab"
    print("[PASS] 4. Frontend UI modal, live telemetry cards & table verified")

    # 5. Verify Voice Action open_analytics
    async def test_voice():
        res = await process_voice_query("May, show analytics", mode="professional")
        assert res["action"] == "open_analytics", f"Expected action 'open_analytics', got {res.get('action')}"
        print(f"[PASS] 5. Voice assistant action verified: '{res['reply']}' -> action={res['action']}")

    asyncio.run(test_voice())

    print("=" * 60)
    print("ALL ANALYTICS TESTS PASSED 100%!")
    print("=" * 60)

if __name__ == "__main__":
    test_analytics_and_ui()
