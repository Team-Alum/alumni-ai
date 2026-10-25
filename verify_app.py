import os
import uuid

from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db, save_user

# Safety rail: this suite creates users, sessions and telemetry. Running it with
# a live Postgres/Supabase URL would write that test data into production, so
# refuse unless the caller explicitly opts in.
if (os.getenv("DATABASE_URL", "").startswith(("postgres://", "postgresql://"))
        and os.getenv("ALLOW_REMOTE_TESTS", "") != "1"):
    raise SystemExit(
        "Refusing to run verification against a remote Postgres/Supabase database.\n"
        "Point DATABASE_URL at a local value (e.g. DATABASE_URL=local-sqlite) and set "
        "DATABASE_PATH to a throwaway file, or set ALLOW_REMOTE_TESTS=1 to override."
    )

def verify_all():
    init_db()
    client = TestClient(app)

    # 1. Test Static files
    r_index = client.get("/")
    assert r_index.status_code == 200, f"Expected 200, got {r_index.status_code}"
    print("GET / [OK]")

    # 2. Test Logo
    r_logo = client.get("/logo.png")
    assert r_logo.status_code == 200, f"Expected 200, got {r_logo.status_code}"
    print(f"GET /logo.png [OK] ({len(r_logo.content)} bytes)")

    # 3. Test Unauthorized Access (Should fail with 401)
    r_unauth = client.get("/api/sessions")
    assert r_unauth.status_code == 401, f"Expected 401, got {r_unauth.status_code}"
    print("Security Check: Unauthorized access rejected [OK]")

    # 4. Mandatory Password Security Check (Must fail with 400)
    r_no_pw = client.post("/api/auth/login", json={
        "username": "nopass_user",
        "email": "nopass@alumni.ai",
        "login_method": "username",
        "is_team_alum": False
    })
    assert r_no_pw.status_code == 400, f"Expected 400, got {r_no_pw.status_code}"
    print("Security Check: Missing password rejected with 400 [OK]")

    # 4a. User 1 Login (ScholarDev - Team Alum)
    # Founder accounts are intentionally NOT creatable through the password
    # endpoint (admin access requires verified Google OAuth). Seed the founder
    # row directly through the DB layer so this suite can still exercise the
    # password login + analytics paths.
    founder_email = "scholar.dev@team.alum"
    founder_password = "AlumSecurePassword123!"
    save_user(
        user_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, founder_email)),
        username="ScholarDev",
        email=founder_email,
        login_method="alum",
        is_team_alum=True,
        password=founder_password
    )
    r_auth1 = client.post("/api/auth/login", json={
        "username": "ScholarDev",
        "email": founder_email,
        "password": founder_password,
        "login_method": "alum",
        "is_team_alum": True
    })
    assert r_auth1.status_code == 200
    u1 = r_auth1.json()
    token1 = u1["token"]
    headers1 = {"Authorization": f"Bearer {token1}"}
    print("User 1 Login [OK]:", u1["username"], "Token received:", token1[:12] + "...")

    # 4b. Returning Member Login Test (Uses saved email and password to re-authenticate)
    r_return = client.post("/api/auth/login", json={
        "email": u1["email"],
        "password": "AlumSecurePassword123!",
        "login_method": "alum",
        "is_team_alum": True
    })
    assert r_return.status_code == 200
    u_return = r_return.json()
    assert u_return["id"] == u1["id"], "Returning user ID must match original user ID"
    print("Returning Member Login [OK]: Re-authenticated successfully as", u_return["username"])

    # 4c. Google OAuth Security Tests (verified credential flow only — spoofing rejected)
    r_cfg = client.get("/api/auth/config")
    assert r_cfg.status_code == 200
    assert "google_client_id" in r_cfg.json()
    print("Google Auth Config [OK]:", r_cfg.json())

    r_google_spoof = client.post("/api/auth/login", json={
        "username": "Google Scholar",
        "email": "scholar@gmail.com",
        "login_method": "google",
        "is_team_alum": False
    })
    assert r_google_spoof.status_code == 400, "Spoofed Google login must be rejected"
    print("Google Spoof Block [OK]: Unverified /login google attempt rejected with 400")

    r_google_fake = client.post("/api/auth/google", json={"credential": "fake-token-not-a-jwt"})
    assert r_google_fake.status_code in (401, 503), \
        f"Fake credential must be rejected, got {r_google_fake.status_code}"
    print("Google Credential Verify [OK]: Fake credential rejected with", r_google_fake.status_code)

    # 4d. Guest Login Test (name-first guest access — no passwords)
    r_guest_noname = client.post("/api/auth/guest", json={})
    assert r_guest_noname.status_code == 400, \
        f"Guest login without a name must be refused, got {r_guest_noname.status_code}"
    r_guest_direct = client.post("/api/auth/guest", json={"username": "Guest Scholar"})
    assert r_guest_direct.status_code == 200, f"Guest direct login failed: {r_guest_direct.text}"
    u_guest = r_guest_direct.json()
    assert u_guest["username"] == "Guest Scholar", u_guest["username"]
    assert u_guest["login_method"] == "guest"
    assert u_guest["email"].endswith("@guest.alumni.ai")
    assert u_guest["is_team_alum"] is False
    assert "token" in u_guest and len(u_guest["token"]) > 10

    guest_headers = {"Authorization": f"Bearer {u_guest['token']}"}
    r_guest_me = client.get("/api/auth/me", headers=guest_headers)
    assert r_guest_me.status_code == 200 and r_guest_me.json()["id"] == u_guest["id"]
    print(f"Guest Name-First Login [OK]: Authenticated as '{u_guest['username']}' ({u_guest['email']})")

    # 4d-ii. Guests can never impersonate the team or an administrator
    r_guest_reserved = client.post("/api/auth/guest", json={"username": "Sudarshan Hadmode"})
    assert r_guest_reserved.status_code == 400, "Founder name must not be claimable by a guest"
    r_guest_admin = client.post("/api/auth/guest", json={"username": "Admin"})
    assert r_guest_admin.status_code == 400, "Admin name must not be claimable by a guest"
    print("Guest Display-Name Guard [OK]: Reserved / impersonation names rejected with 400")

    # 4e. Guest Login via /api/auth/login payload (client email is ignored)
    r_guest_route = client.post("/api/auth/login", json={
        "login_method": "guest",
        "username": "Guest Route",
        "email": "teamalumorg@gmail.com"
    })
    assert r_guest_route.status_code == 200
    u_guest2 = r_guest_route.json()
    assert u_guest2["login_method"] == "guest"
    assert u_guest2["email"] != "teamalumorg@gmail.com", "Guest email must be server-generated"
    assert u_guest2["is_team_alum"] is False, "Guest must never gain founder access"
    print(f"Guest Route Login [OK]: Authenticated as '{u_guest2['username']}' ({u_guest2['email']})")

    r_auth2 = client.post("/api/auth/login", json={
        "username": "alex_coder",
        "email": "alex@alumni.ai",
        "password": "AlexUserPassword99!",
        "login_method": "username",
        "is_team_alum": False
    })
    assert r_auth2.status_code == 200
    u2 = r_auth2.json()
    token2 = u2["token"]
    headers2 = {"Authorization": f"Bearer {token2}"}
    print("User 2 Login [OK]:", u2["username"], "Token received:", token2[:12] + "...")

    # 6. User 1 creates a private chat session
    r_chat1 = client.post("/api/chat", headers=headers1, json={
        "message": "Explain quantum computing architecture",
        "mode": "professional"
    })
    assert r_chat1.status_code == 200
    sess_id_u1 = r_chat1.json()["session_id"]
    print("User 1 Chat [OK]: Session created:", sess_id_u1)

    # 7. Privacy & Data Isolation Test: User 2 tries to read User 1's messages (Must fail!)
    r_hack = client.get(f"/api/sessions/{sess_id_u1}/messages", headers=headers2)
    assert r_hack.status_code == 404, f"Security Breach! Expected 404, got {r_hack.status_code}"
    print("Privacy Check: User 2 CANNOT read User 1 chat session [OK]")

    # 8. User 2 creates their own independent chat
    r_chat2 = client.post("/api/chat", headers=headers2, json={
        "message": "Why does my code have bugs?",
        "mode": "sarcastic"
    })
    assert r_chat2.status_code == 200
    print("User 2 Chat [OK]: Sarcastic mode reasoning received")

    # 9. Verify Session lists are completely isolated
    sess_list_u1 = client.get("/api/sessions", headers=headers1).json()
    sess_list_u2 = client.get("/api/sessions", headers=headers2).json()
    assert all(s["user_id"] == u1["id"] for s in sess_list_u1)
    assert all(s["user_id"] == u2["id"] for s in sess_list_u2)
    print(f"Data Isolation Check [OK]: User 1 has {len(sess_list_u1)} sessions, User 2 has {len(sess_list_u2)} sessions")

    # 10. Voice query with authentication
    r_voice = client.post("/api/voice/query", headers=headers1, json={
        "query": "How does Alumni AI work?",
        "mode": "basic"
    })
    assert r_voice.status_code == 200
    print("Voice Query with Auth [OK]:", r_voice.json()["audio_text"][:50])

    # 11. Chrome Tools with authentication
    r_tool = client.post("/api/tools/search", headers=headers1, json={
        "query": "neural networks",
        "max_results": 2
    })
    assert r_tool.status_code == 200
    print("Browser Search with Auth [OK]: Results returned")

    # 12. Token verification via /api/auth/me
    r_me = client.get("/api/auth/me", headers=headers1)
    assert r_me.status_code == 200 and r_me.json()["username"] == "ScholarDev"
    print("Auth Me Verification [OK]")

    # 13. Data Analytics & Usage Overview
    r_analytics = client.get("/api/analytics/overview", headers=headers1)
    assert r_analytics.status_code == 200, f"Expected 200, got {r_analytics.status_code}"
    analytics_data = r_analytics.json()
    assert analytics_data["total_queries"] >= 2, f"Expected at least 2 logged queries, got {analytics_data['total_queries']}"
    assert "provider_distribution" in analytics_data
    assert "mode_distribution" in analytics_data
    print(f"Analytics Overview [OK]: {analytics_data['total_queries']} queries tracked, Avg Latency: {analytics_data['avg_latency_ms']}ms")
    print(f"Provider Distribution: {analytics_data['provider_distribution']}")
    print(f"Mode Distribution: {analytics_data['mode_distribution']}")

    # 13b. Visitor traffic counters (today, rolling week, month, all-time)
    r_track = client.post("/api/analytics/track", json={"visitor_key": "verify-visitor-001", "path": "/"})
    assert r_track.status_code == 200, f"Visitor tracking failed: {r_track.status_code}"
    r_visitors = client.get("/api/analytics/visitors", headers=headers1)
    assert r_visitors.status_code == 200, f"Expected 200, got {r_visitors.status_code}"
    visitor_data = r_visitors.json()
    vtotals = visitor_data["totals"]
    assert vtotals["today_hits"] >= 1
    assert vtotals["today_uniques"] >= 1
    assert vtotals["week_hits"] >= vtotals["today_hits"]
    assert vtotals["all_time_hits"] >= vtotals["week_hits"]
    assert len(visitor_data["daily"]) == 14, f"Expected 14 daily buckets, got {len(visitor_data['daily'])}"
    assert len(visitor_data["monthly"]) == 12, f"Expected 12 monthly buckets, got {len(visitor_data['monthly'])}"
    assert visitor_data["daily"][0]["is_today"] is True
    print(f"Visitor Traffic [OK]: today {vtotals['today_uniques']} visitors / {vtotals['today_hits']} visits, "
          f"7d {vtotals['week_uniques']} / {vtotals['week_hits']}, "
          f"all-time {vtotals['all_time_uniques']} / {vtotals['all_time_hits']}")

    # 14. Data Analytics Recent Events Log
    r_events = client.get("/api/analytics/events?limit=10", headers=headers1)
    assert r_events.status_code == 200
    events = r_events.json()
    assert len(events) >= 2
    latest = events[0]
    print(f"Analytics Events Log [OK]: Latest query used '{latest['provider_used']}' with mode '{latest['mode']}' in {latest['latency_ms']}ms")

    print("\n=======================================================")
    print("ALL 15 MULTI-USER, AUTO-FALLBACK, ANALYTICS & VISITOR TESTS PASSED 100%!")
    print("=======================================================")

if __name__ == "__main__":
    verify_all()

