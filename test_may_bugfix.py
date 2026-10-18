import asyncio
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.voice_service import process_voice_query

async def run_regression_tests():
    print("=" * 70)
    print("RUNNING MAY VOICE ASSISTANT REGRESSION SUITE (10 SCENARIOS)")
    print("=" * 70)

    test_cases = [
        # 1. Self-introduction
        {
            "id": 1,
            "query": "Introduce yourself.",
            "check": lambda r: ("may" in r.lower() or "voice assistant" in r.lower()) and "simple hai. iska basic concept" not in r.lower(),
            "desc": "Introduce yourself returns natural identity, not generic concept template"
        },
        # 2. Conceptual / Definition
        {
            "id": 2,
            "query": "What is artificial intelligence?",
            "check": lambda r: any(k in r.lower() for k in ["computer", "machine", "intelligence", "learn", "human"]) and "agar aapko what is artificial intelligence" not in r.lower(),
            "desc": "What is artificial intelligence returns accurate AI definition"
        },
        # 3. Scientific law
        {
            "id": 3,
            "query": "Explain Newton's second law.",
            "check": lambda r: ("force" in r.lower() or "acceleration" in r.lower() or "f =" in r.lower() or "f equals" in r.lower()) and "agar aapko explain newton" not in r.lower(),
            "desc": "Explain Newton's second law returns F = ma force/mass/acceleration dynamics"
        },
        # 4. Math with words
        {
            "id": 4,
            "query": "What is 25 multiplied by 4?",
            "check": lambda r: "100" in r and "agar aapko what is 25" not in r.lower(),
            "desc": "What is 25 multiplied by 4 returns concise '100.'"
        },
        # 5. Joke request
        {
            "id": 5,
            "query": "Tell me a joke.",
            "check": lambda r: len(r.strip()) > 15 and "agar aapko tell me a joke" not in r.lower(),
            "desc": "Tell me a joke returns an appropriate joke rather than generic template"
        },
        # 6. Detailed structured explanation
        {
            "id": 6,
            "query": "Explain rotational motion in detail.",
            "check": lambda r: any(k in r.lower() for k in ["torque", "axis", "inertia", "angular", "rotate", "rotat"]) and "agar aapko explain rotational" not in r.lower(),
            "desc": "Explain rotational motion in detail returns physics explanation of torque/inertia"
        },
        # 7. Follow-up question using context
        {
            "id": 7,
            "query": "Can you give an example of this?",
            "history": [
                {"sender": "user", "content": "Explain Newton's second law."},
                {"sender": "assistant", "content": "Newton's second law states that Force equals mass times acceleration (F = ma)."}
            ],
            "check": lambda r: any(k in r.lower() for k in ["ball", "force", "acceleration", "hit", "cricket", "example", "push"]) and "agar aapko can you give" not in r.lower(),
            "desc": "Follow-up question uses conversation history to supply relevant example"
        },
        # 8. Hindi in Roman script
        {
            "id": 8,
            "query": "Aap kaise ho?",
            "check": lambda r: any(k in r.lower() for k in ["badhiya", "theek", "hoon", "help", "madad", "great", "fine"]) and "agar aapko aap kaise ho" not in r.lower(),
            "desc": "Hindi in Roman script ('Aap kaise ho?') answered in natural Hinglish"
        },
        # 9. English query
        {
            "id": 9,
            "query": "How are you today?",
            "check": lambda r: any(k in r.lower() for k in ["great", "doing", "good", "ready", "assist", "well"]) and "agar aapko how are you" not in r.lower(),
            "desc": "English query answered naturally and helpfully"
        },
        # 10. Honest uncertainty response
        {
            "id": 10,
            "query": "Will it rain on Mars tomorrow at 3 PM?",
            "check": lambda r: any(k in r.lower() for k in ["cannot", "never", "will not", "not possible", "sambhav nahi", "uncertain", "predict", "exact", "impossible", "no"]) and "agar aapko will it rain" not in r.lower(),
            "desc": "Unpredictable question returns honest uncertainty without fabricating facts"
        }
    ]

    passed = 0
    total = len(test_cases)

    for tc in test_cases:
        conv_hist = tc.get("history")
        res = await process_voice_query(
            query=tc["query"],
            mode="professional",
            user={"id": "test_user_regression", "username": "Sudarshan", "login_method": "alum"},
            conversation_history=conv_hist
        )
        reply = res.get("reply", "")
        provider = res.get("provider", "")
        success = tc["check"](reply)
        
        status_tag = "[PASS]" if success else "[FAIL]"
        print(f"\n{status_tag} Test {tc['id']}: {tc['desc']}")
        print(f"       User Query: '{tc['query']}'")
        print(f"       Provider Used: {provider}")
        print(f"       May Response: \"{reply[:120]}{'...' if len(reply) > 120 else ''}\"")

        if success:
            passed += 1

    print("\n" + "=" * 70)
    print(f"REGRESSION SUITE COMPLETED: {passed}/{total} TESTS PASSED ({int(passed/total*100)}%)")
    print("=" * 70)
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(run_regression_tests())
    if not success:
        sys.exit(1)
