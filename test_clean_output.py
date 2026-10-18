import asyncio
import re
from app.services.ai_service import (
    BASE_SYSTEM_INSTRUCTION,
    get_system_instruction,
    clean_ai_response,
    generate_ai_response
)
from app.services.voice_service import process_voice_query

def test_base_system_instructions():
    print("Testing Base System Instructions across all modes...")
    modes = ["professional", "basic", "sarcastic", "chrome", "may"]
    for m in modes:
        inst = get_system_instruction(m)
        assert "SILENT REASONING ONLY" in inst, f"Missing SILENT REASONING constraint in mode {m}"
        assert "NO META-COMMENTARY" in inst, f"Missing NO META-COMMENTARY constraint in mode {m}"
        assert "CLEAN MARKDOWN FORMATTING" in inst, f"Missing CLEAN MARKDOWN FORMATTING constraint in mode {m}"
        assert "You are Alumni AI" in inst, f"Missing identity header in mode {m}"
    print("Base System Instructions: Verified for all 5 modes [PASS]")

def test_clean_ai_response_filter():
    print("Testing clean_ai_response regex filter...")
    sample_think = "<think>\nThinking about quicksort...\nPivot selection: median-of-three\n</think>\n\n### Quicksort Implementation\n```python\nprint(1)\n```"
    cleaned = clean_ai_response(sample_think)
    assert "<think>" not in cleaned, "Failed: <think> tag was not stripped"
    assert "</think>" not in cleaned, "Failed: </think> tag was not stripped"
    assert "Thinking about quicksort" not in cleaned, "Failed: internal reasoning was not stripped"
    assert "### Quicksort Implementation" in cleaned, "Failed: legitimate content was lost"

    sample_thought = "<thought>Internal monologue</thought>Direct Answer"
    assert clean_ai_response(sample_thought) == "Direct Answer"

    sample_preamble = "<think>Planning</think>\n\nHere is your response:\nDirect Answer"
    assert clean_ai_response(sample_preamble) == "Direct Answer"
    print("clean_ai_response filter: Verified with zero leakage [PASS]")

async def test_live_ai_modes_cleanliness():
    print("Testing live generation across all modes for clean outputs...")
    modes = ["professional", "basic", "sarcastic"]
    query = "Explain binary search in 2 sentences."
    for m in modes:
        res = await generate_ai_response(query, mode=m)
        text = str(res)
        assert "<think>" not in text.lower(), f"Leakage detected in mode {m}: <think> found"
        assert "<thought>" not in text.lower(), f"Leakage detected in mode {m}: <thought> found"
        assert "<scratchpad>" not in text.lower(), f"Leakage detected in mode {m}: <scratchpad> found"
        assert len(text.strip()) > 10, f"Empty response in mode {m}"
        print(f"Mode [{m.upper()}] Clean Output Verified (Provider: {res.provider}, Length: {len(text)} chars) [PASS]")

    voice_res = await process_voice_query("What is RAM?", mode="basic")
    assert "<think>" not in voice_res["reply"].lower(), "Leakage in May voice assistant"
    assert "<think>" not in voice_res["audio_text"].lower(), "Leakage in May audio text"
    print("May Voice Assistant Clean Output Verified [PASS]")

def main():
    test_base_system_instructions()
    test_clean_ai_response_filter()
    asyncio.run(test_live_ai_modes_cleanliness())
    print("\nALL REASONING LEAKAGE PREVENTION CHECKS PASSED 100%!")

if __name__ == "__main__":
    main()
