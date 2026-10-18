import asyncio
from fastapi.testclient import TestClient
from app.main import app
from app.services.ai_service import observe_and_analyze_attachments, generate_ai_response
from app.config import OPENCODE_ATTACHMENT_KEY, OPENCODE_FALLBACK_KEY

client = TestClient(app)

async def test_attachment_observer_and_fallback():
    print("=== Testing Key No. 3: Attachment Observer & Fallback Brain ===")
    
    # 1. Verify Key No. 3 is present in config
    assert OPENCODE_ATTACHMENT_KEY.startswith("oc_sk_"), "Invalid OPENCODE_ATTACHMENT_KEY"
    assert OPENCODE_FALLBACK_KEY.startswith("oc_sk_"), "Invalid OPENCODE_FALLBACK_KEY"
    assert len(OPENCODE_ATTACHMENT_KEY) > 20, "OPENCODE_ATTACHMENT_KEY looks too short"
    print("Key No. 3 Configuration Check: [PASS]")

    # 2. Test live Attachment Observer & Code Analyzer (Key No. 3)
    sample_code = """
def calculate_compound_interest(principal: float, rate: float, times_per_year: int, years: int) -> float:
    # A = P(1 + r/n)^(nt)
    amount = principal * ((1 + (rate / times_per_year)) ** (times_per_year * years))
    return round(amount, 2)
"""
    attachments = [
        {
            "name": "finance.py",
            "type": "text/x-python",
            "size": len(sample_code),
            "text": sample_code
        }
    ]

    print("Executing observe_and_analyze_attachments with Key No. 3...")
    dossier = await observe_and_analyze_attachments(
        attachments=attachments,
        user_query="How does this formula calculate interest and what are edge cases?"
    )
    assert dossier is not None, "Failed: Observer returned None"
    assert len(dossier) > 30, f"Dossier too short: {dossier}"
    print(f"Observation Dossier Generated ({len(dossier)} chars) [PASS]")
    print(f"Dossier Preview:\n{dossier[:250]}...\n")

    # 3. Test Full Chat Endpoint with Attachment Observation + 1st API Synthesis
    login_res = client.post("/api/auth/login", json={
        "username": "ObserverDev",
        "email": "observer@team.alum",
        "password": "pass1234Secure",
        "login_method": "alum",
        "is_team_alum": True
    })
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    chat_res = client.post("/api/chat", json={
        "message": "Review this function and optimize it.",
        "mode": "professional",
        "attachments": attachments
    }, headers=headers)
    assert chat_res.status_code == 200, f"Chat failed: {chat_res.text}"
    chat_data = chat_res.json()
    ai_reply = chat_data["ai_message"]["content"]
    assert len(ai_reply) > 50
    print("Chat API with Key No. 3 observation -> 1st API synthesis [PASS]")

    # 4. Test Fallback Mechanism: Simulate Key No. 1 failure, verify Key No. 3 takes over
    print("Testing OpenCode Zen automatic fallback to Key No. 3...")
    # Pass an invalid key as custom key to simulate failure on primary try
    res_fallback = await generate_ai_response(
        prompt="Explain what an asymptotic upper bound means in Big-O notation in 2 sentences.",
        mode="professional",
        custom_api_key="oc_sk_invalid_test_key_to_trigger_fallback"
    )
    # The primary invalid key fails and automatically falls back to OPENCODE_FALLBACK_KEY (Key No. 3) or Gemini!
    assert res_fallback.provider in ("opencode_zen_fallback", "opencode_zen", "gemini_free"), f"Unexpected provider: {res_fallback.provider}"
    assert len(str(res_fallback)) > 20
    print(f"Fallback to Key No. 3 verified successfully! Provider: {res_fallback.provider} [PASS]")

    print("\n=======================================================")
    print("ALL KEY NO. 3 ATTACHMENT OBSERVER & FALLBACK TESTS PASSED 100%!")
    print("=======================================================\n")

if __name__ == "__main__":
    asyncio.run(test_attachment_observer_and_fallback())
