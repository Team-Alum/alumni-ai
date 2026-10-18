import asyncio
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.voice_service import (
    process_voice_query,
    detect_query_language,
    format_for_speech_synthesis,
    STOP_WORDS,
    ACK_WORDS
)
from app.services.ai_service import fallback_generate, clean_ai_response

async def run_tests():
    print("=" * 60)
    print("RUNNING MAY VOICE ASSISTANT COMPREHENSIVE VERIFICATION SUITE")
    print("=" * 60)
    passed = 0
    total = 0

    def assert_test(cond, title):
        nonlocal passed, total
        total += 1
        if cond:
            print(f"[PASS] {title}")
            passed += 1
        else:
            print(f"[FAIL] {title}")

    # Scenario 1: Authenticated user display name
    auth_user = {"id": "test_user_1", "username": "Aarav", "login_method": "google"}
    res_auth = await process_voice_query("Hello May", mode="professional", user=auth_user)
    assert_test(isinstance(res_auth.get("reply"), str) and len(res_auth["reply"]) > 0, "Scenario 1: Authenticated user query processed successfully")

    # Scenario 2: Guest user (no fabricated name)
    guest_user = {"id": "guest_123", "username": "Guest_9921", "login_method": "guest"}
    res_guest = await process_voice_query("Who am I?", mode="professional", user=guest_user)
    reply_lower = res_guest.get("reply", "").lower()
    assert_test("guest_9921" not in reply_lower and "sudarshan" not in reply_lower and "soham" not in reply_lower, "Scenario 2: Guest user not addressed with fabricated name or developer name")

    # Scenario 3: Developer names not injected into ordinary queries
    res_math = await process_voice_query("What is 15 squared?", mode="professional", user=auth_user)
    reply_math = res_math.get("reply", "").lower()
    assert_test("sudarshan" not in reply_math and "soham" not in reply_math, "Scenario 3: Developer names NOT injected into math/ordinary queries")

    # Scenario 4: Hindi and Hinglish language detection & formatting
    lang_hi = detect_query_language("May, ye kaise kaam karta hai?")
    lang_en = detect_query_language("What is the time complexity of quicksort?")
    lang_devanagari = detect_query_language("नमस्ते, आप कैसी हैं?")
    assert_test(lang_hi == "hi-IN" and lang_devanagari == "hi-IN" and lang_en == "en-IN", f"Scenario 4: Language detection correctly routes hi-IN and en-IN (got {lang_hi}, {lang_devanagari}, {lang_en})")

    # Scenario 5: Simple questions receive concise answers (15 squared -> 225.)
    fallback_math = fallback_generate("What is 15 squared?", mode="may")
    assert_test("225" in fallback_math and len(fallback_math.strip()) <= 10, f"Scenario 5: Simple math query receives concise answer: '{fallback_math}'")

    # Scenario 6: Detailed requests receive comprehensive breakdown
    fallback_detail = fallback_generate("Explain this in detail", mode="may")
    assert_test(len(fallback_detail) > 100 and "step" in fallback_detail.lower(), "Scenario 6: Detailed request receives thorough, non-truncated explanation")

    # Scenario 7: Text formatting for speech synthesis (no markdown fences, proper pauses)
    raw_md = "Here is the code:\n```python\nprint('Hello')\n```\nCheck **bold** and `code` and AI API!"
    formatted_speech = format_for_speech_synthesis(raw_md)
    assert_test("```" not in formatted_speech and "**" not in formatted_speech and "A.I." in formatted_speech and "A.P.I." in formatted_speech, f"Scenario 7: Clean formatting for speech synthesis without raw markdown ({formatted_speech})")

    # Scenario 8: Pure acknowledgment produces silence (Speak Less, Listen More)
    res_ack1 = await process_voice_query("okay", mode="professional", user=auth_user)
    res_ack2 = await process_voice_query("theek hai", mode="professional", user=auth_user)
    assert_test(res_ack1.get("should_speak") is False and res_ack2.get("should_speak") is False, "Scenario 8: Acknowledgments ('okay', 'theek hai') yield should_speak=False")

    # Scenario 9: Stop words trigger immediate stop action and silence
    res_stop1 = await process_voice_query("stop", mode="professional", user=auth_user)
    res_stop2 = await process_voice_query("bas", mode="professional", user=auth_user)
    assert_test(res_stop1.get("action") == "stop" and res_stop1.get("should_speak") is False and res_stop2.get("action") == "stop" and res_stop2.get("should_speak") is False, "Scenario 9: Stop and Bas trigger action='stop' and should_speak=False")

    # Scenario 10: UI voice actions (e.g. open settings)
    res_settings = await process_voice_query("open settings", mode="professional", user=auth_user)
    assert_test(res_settings.get("action") == "open_settings" and res_settings.get("should_speak") is True, f"Scenario 10: Voice command 'open settings' parsed with action='{res_settings.get('action')}'")

    # Scenario 11: Developer identity returned ONLY when explicitly asked
    res_identity = fallback_generate("Who created Alumni AI?", mode="may")
    assert_test("Sudarshan" in res_identity and "Soham" in res_identity and "Team Alum" in res_identity, "Scenario 11: Team Alum creators accurately identified when explicitly asked")

    # Scenario 12: TTS resilience (graceful fallback if audio synthesis returns None)
    res_offline = await process_voice_query("Hello May", speaker="unknown_speaker", language="en-IN")
    assert_test(res_offline.get("reply") is not None and res_offline.get("provider") in ["sarvam_bulbul_neural", "webspeech_fallback"], "Scenario 12: Application never crashes on TTS failure; provides graceful audio fallback")

    print("=" * 60)
    print(f"VERIFICATION COMPLETE: {passed}/{total} TESTS PASSED ({int(passed/total*100)}%)")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_tests())
