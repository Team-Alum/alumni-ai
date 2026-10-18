import asyncio
import uuid
from app.database import init_db, save_user, create_session, save_message, get_messages_by_session
from app.services.ai_service import fallback_generate, generate_ai_response
from app.services.voice_service import process_voice_query

def run_tests():
    init_db()
    uid = f"u_{uuid.uuid4().hex[:6]}"
    sid = f"s_{uuid.uuid4().hex[:6]}"
    user = save_user(uid, "test_dev", f"{uid}@alum.ai", "username", False)
    sess = create_session(sid, uid, "Test Session", "general", "professional")
    save_message(sid, "user", "What is recursion?")
    ai_reply = fallback_generate("What is recursion?", "professional")
    save_message(sid, "ai", ai_reply)
    history = get_messages_by_session(sid)

    print(f"User: {user['username']}")
    print(f"Session: {sess['title']}")
    print(f"Messages count: {len(history)}")

    async def test_async():
        res_prof = await generate_ai_response("Write quicksort in python", mode="professional")
        res_sarc = await generate_ai_response("Write quicksort in python", mode="sarcastic")
        res_basic = await generate_ai_response("Write quicksort in python", mode="basic")
        voice_res = await process_voice_query("Debug my script", mode="sarcastic")
        print("Professional snippet length:", len(res_prof))
        print("Sarcastic snippet length:", len(res_sarc))
        print("Basic snippet length:", len(res_basic))
        print("Voice reply sample:", voice_res["reply"][:60])

    asyncio.run(test_async())
    print("SUCCESS: All backend tests passed!")

if __name__ == "__main__":
    run_tests()
