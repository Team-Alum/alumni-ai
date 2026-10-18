from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db

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
    r_auth1 = client.post("/api/auth/login", json={
        "username": "ScholarDev",
        "email": "scholar.dev@team.alum",
        "password": "AlumSecurePassword123!",
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

    # 4d. Guest Login Test (Fast 1-Click instant guest access, no passwords)
    r_guest_direct = client.post("/api/auth/guest")
    assert r_guest_direct.status_code == 200, f"Guest direct login failed: {r_guest_direct.text}"
    u_guest = r_guest_direct.json()
    assert u_guest["username"].startswith("Guest")
    assert u_guest["login_method"] == "guest"
    assert "token" in u_guest and len(u_guest["token"]) > 10
    
    guest_headers = {"Authorization": f"Bearer {u_guest['token']}"}
    r_guest_me = client.get("/api/auth/me", headers=guest_headers)
    assert r_guest_me.status_code == 200 and r_guest_me.json()["id"] == u_guest["id"]
    print(f"Guest 1-Click Login [OK]: Authenticated as '{u_guest['username']}' ({u_guest['email']})")

    # 4e. Guest Login via /api/auth/login payload
    r_guest_route = client.post("/api/auth/login", json={
        "login_method": "guest"
    })
    assert r_guest_route.status_code == 200
    u_guest2 = r_guest_route.json()
    assert u_guest2["login_method"] == "guest"
    print(f"Guest Route Login [OK]: Authenticated as '{u_guest2['username']}'")

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

    # 14. Data Analytics Recent Events Log
    r_events = client.get("/api/analytics/events?limit=10", headers=headers1)
    assert r_events.status_code == 200
    events = r_events.json()
    assert len(events) >= 2
    latest = events[0]
    print(f"Analytics Events Log [OK]: Latest query used '{latest['provider_used']}' with mode '{latest['mode']}' in {latest['latency_ms']}ms")

    print("\n=======================================================")
    print("ALL 14 MULTI-USER, AUTO-FALLBACK & ANALYTICS TESTS PASSED 100%!")
    print("=======================================================")

if __name__ == "__main__":
    verify_all()

