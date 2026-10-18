import asyncio
from fastapi.testclient import TestClient
from app.main import app
from app.services.voice_service import process_voice_query

client = TestClient(app)

def test_analytics_and_ui():
    print("=" * 60)
    print("RUNNING ANALYTICS SUITE & UI VERIFICATION")
    print("=" * 60)

    # 1. Login to get token
    login_res = client.post("/api/auth/login", json={
        "username": "FounderSudarshan",
        "email": "sudarshan.deve@gmail.com",
        "password": "superSafePassword123",
        "login_method": "alum",
        "is_team_alum": True
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["token"]
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
    print(f"[PASS] 2. /api/analytics/overview active: {data['total_users']} users, {data['total_queries']} queries, {data['total_sessions']} sessions")

    # 3. Test /api/analytics/events
    events_res = client.get("/api/analytics/events?limit=10", headers=headers)
    assert events_res.status_code == 200, f"Events endpoint failed: {events_res.text}"
    events = events_res.json()
    assert isinstance(events, list)
    print(f"[PASS] 3. /api/analytics/events active: {len(events)} recent events retrieved")

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
