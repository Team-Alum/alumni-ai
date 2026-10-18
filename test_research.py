import asyncio
from fastapi.testclient import TestClient
from app.main import app

def test_research_pipeline():
    client = TestClient(app)

    # 1. Reject unauthenticated access
    r_unauth = client.get("/api/research/suggestions")
    assert r_unauth.status_code == 401, f"Expected 401, got {r_unauth.status_code}"
    print("[PASS] Unauthenticated access properly rejected (401)")

    # 2. Authenticate user
    login_resp = client.post("/api/auth/login", json={
        "username": "ResearchScholar",
        "email": "",
        "password": "AlumSecurePassword123!",
        "login_method": "alum",
        "is_team_alum": True
    })
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("[PASS] User authenticated successfully with token")

    # 3. Test suggestions endpoint
    r_sug = client.get("/api/research/suggestions", headers=headers)
    assert r_sug.status_code == 200, f"Suggestions failed: {r_sug.text}"
    suggestions = r_sug.json()
    assert len(suggestions) >= 4, f"Expected at least 4 suggestions, got {len(suggestions)}"
    for s in suggestions:
        assert "category" in s and "title" in s and "query" in s
    print(f"[PASS] Suggestions endpoint returned {len(suggestions)} structured items")

    # 4. Test Dedicated Two-Tier Research API (POST /api/research)
    test_query = "What are the latest AI agent frameworks in 2026?"
    r_research = client.post("/api/research", headers=headers, json={
        "query": test_query,
        "mode": "professional",
        "depth": "deep"
    })
    assert r_research.status_code == 200, f"Research endpoint failed: {r_research.text}"
    data = r_research.json()
    assert data["query"] == test_query
    assert "sources" in data and isinstance(data["sources"], list)
    assert len(data["sources"]) > 0, "Research API should gather real sources"
    assert "answer" in data and len(data["answer"]) > 50, "First API should synthesize an analytical answer"
    assert "suggested_questions" in data and isinstance(data["suggested_questions"], list)
    assert len(data["suggested_questions"]) >= 3, "Suggestion engine should provide at least 3 follow-up questions"
    print(f"[PASS] Two-Tier Research API successful!")
    print(f"       - Sources gathered: {len(data['sources'])}")
    print(f"       - Answer length: {len(data['answer'])} chars")
    print(f"       - Suggested questions: {data['suggested_questions']}")

    # 5. Test Chat Route with web_research=True flag
    r_chat = client.post("/api/chat", headers=headers, json={
        "message": "Research Python 3.13 free-threading performance benchmarks",
        "mode": "professional",
        "web_research": True
    })
    assert r_chat.status_code == 200, f"Chat research failed: {r_chat.text}"
    chat_data = r_chat.json()
    assert "ai_message" in chat_data
    assert "sources" in chat_data and chat_data["sources"] is not None
    assert "suggested_questions" in chat_data and chat_data["suggested_questions"] is not None
    assert len(chat_data["suggested_questions"]) >= 3
    print(f"[PASS] Chat integration with web_research flag verified!")

    print("\n=======================================================")
    print("ALL TWO-TIER WEB RESEARCH & QUESTION SUGGESTION TESTS PASSED 100%!")
    print("=======================================================\n")

if __name__ == "__main__":
    test_research_pipeline()
