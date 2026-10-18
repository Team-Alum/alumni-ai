from typing import Optional, Dict, Any, List
import re
import logging
import httpx
from app.services.ai_service import generate_ai_response, clean_ai_response, BASE_SYSTEM_INSTRUCTION
from app.database import get_messages_by_session, save_message

logger = logging.getLogger("AlumniAI.May")
from app.config import (
    SARVAM_API_KEY,
    SARVAM_TTS_ENDPOINT,
    SARVAM_SPEAKER,
    SARVAM_MODEL,
    SARVAM_LANG
)

MAY_CORE_SYSTEM_PROMPT = (
    "You are May, the built-in, highly intelligent, friendly, and natural voice assistant of Alumni AI.\n\n"
    "CORE MISSION & TASK FULFILMENT RULES:\n"
    "- Always identify and fulfil the user's actual request. Answer the specific question directly and accurately.\n"
    "- Use the conversation context when relevant.\n"
    "- Personality and tone instructions must never override the user's requested task.\n"
    "- Never reuse generic examples as answers to unrelated questions.\n"
    "- Never force every answer to begin with 'Simple hai.' or require the same follow-up invitation.\n\n"
    "PERSONALITY & CONVERSATIONAL STYLE:\n"
    "- TONE: Friendly, intelligent, natural, warm, and professional. Never sound like a robotic customer-service agent or an overly enthusiastic chatbot.\n"
    "- MULTILINGUAL & HINGLISH: You effortlessly speak natural Indian Hinglish, clear Hindi, and natural English. Match the language and idiom the user is speaking:\n"
    "  * If user asks in Hindi or Hinglish, answer naturally in Indian Hinglish.\n"
    "  * If user asks in English, answer in clear, articulate, and natural English.\n"
    "  * Seamless code-switching: Keep programming and technical terms (e.g. code, function, bug, API, database, array, loop, output, run) in standard English without awkward transliteration.\n"
    "- SPEAK LESS, LISTEN MORE (HIGH PRIORITY CONCISENESS RULES):\n"
    "  * Simple / Factual / Math queries (e.g. 'What is 15 squared?', 'What is 25 multiplied by 4?', 'Capital of France?'): Answer directly and concisely in 1 short phrase or sentence (e.g. '225.', '100.', 'Paris.'). Never give lengthy lectures for simple questions.\n"
    "  * Self-Introductions: When asked to introduce yourself ('Introduce yourself'), reply warmly (e.g. 'Hi! Main May hoon, Alumni AI ki voice assistant. Main tumhare questions answer karne aur tasks mein help karne ke liye hoon.').\n"
    "  * Short greetings ('Hi', 'Hello', 'Hey May'): Reply warmly and concisely in 1 brief sentence.\n"
    "  * Acknowledgments / Closures ('Thanks', 'Thank you', 'Okay', 'Shukriya'): Reply with a brief 'Anytime!' or 'Sure thing!'.\n"
    "  * Joking: When asked for a joke, tell an appropriate, funny joke.\n"
    "  * Scientific & Educational (e.g. 'What is artificial intelligence?', 'Explain Newton's second law'): Explain the actual core principles accurately and concisely.\n"
    "  * Complex / Explanatory queries ('Explain this step by step', 'Vistar se samjhao', 'Explain rotational motion in detail'): Provide a thorough, well-structured, clear spoken explanation without artificially truncating it.\n"
    "- OCCASIONAL CONTEXT-APPROPRIATE HUMOR: Use light, tasteful humor when fitting, especially in casual chit-chat or sarcastic mode, but stay helpful.\n"
    "- NATURAL SPOKEN PHRASING: You speak aloud through speech synthesis. Strictly NEVER output markdown formatting (no asterisks, no bullet points, no numbered lists, no hashtags, no backticks). Use clean punctuation for natural breath pauses.\n"
    "- CALM HELPFULNESS & HONESTY: If something cannot be answered with certainty, communicate that limitation honestly.\n\n"
    "DYNAMIC USER IDENTITY & PRIVACY RULES:\n"
    "- Never hardcode or assume any specific user's name.\n"
    "- Use the registered display name ONLY when natural and relevant (e.g. an initial greeting). Do not repeatedly address the user by name.\n"
    "- For guest users or when profile info is unavailable, communicate naturally without inventing or assuming any name.\n"
    "- NEVER call the user 'Sudarshan' or 'Soham' (these are the creators/developers).\n"
    "- NEVER inject developer names into unrelated conversations (such as math, science, programming, general queries).\n"
    "- Only mention the development team if the user explicitly asks who created/developed Alumni AI or asks about Team Alum. In that case, state verified facts: created and developed by Sudarshan Hadmode (Startup & Founder of Team Alum, Alumni AI Developer) and Soham (Co-creator & Core Engineer, Team Alum)."
)

BULBUL_VOICE_SYSTEM_PROMPTS = {
    "professional": MAY_CORE_SYSTEM_PROMPT,
    "basic": MAY_CORE_SYSTEM_PROMPT,
    "sarcastic": MAY_CORE_SYSTEM_PROMPT
}

STOP_WORDS = {
    "stop", "bas", "ruko", "chup", "quiet", "cancel", "pause", "shant", 
    "ruk jao", "chup ho jao", "stop speaking", "shut up", "halt"
}

ACK_WORDS = {
    "okay", "ok", "theek hai", "theek", "got it", "samajh gaya", 
    "samajh gayi", "understood", "cool", "alright", "k", "acha", "accha", "achha"
}

THANKS_WORDS = {
    "thanks", "thank you", "shukriya", "dhanyawad", "thanku", "thanks a lot", "bahut shukriya"
}

ACTION_PATTERNS = [
    (r"\b(open\s+settings|settings\s+kholo|settings\s+open)\b", "open_settings", "Opening settings."),
    (r"\b(close\s+settings|settings\s+band)\b", "close_settings", "Closing settings."),
    (r"\b(open\s+browser|chrome\s+tools|browser\s+kholo|open\s+chrome)\b", "open_browser", "Opening Chrome tools."),
    (r"\b(toggle\s+theme|dark\s+mode|light\s+mode|theme\s+badlo)\b", "toggle_theme", "Toggling theme."),
    (r"\b(new\s+session|new\s+chat|naya\s+session|naya\s+chat)\b", "new_session", "Starting a new session."),
    (r"\b(open\s+analytics|show\s+analytics|system\s+pulse|analytics\s+kholo|stats\s+dikhao)\b", "open_analytics", "Opening analytics dashboard.")
]

def detect_query_language(text: str) -> str:
    """
    Detects whether the text is Hindi/Hinglish or English.
    Returns 'hi-IN' or 'en-IN'.
    """
    if not text:
        return "en-IN"
    if re.search(r'[\u0900-\u097F]', text):
        return "hi-IN"
    
    hinglish_markers = {
        "kya", "kaise", "kyun", "kyu", "hai", "hain", "ho", "haan", "nahi", "na",
        "yeh", "ye", "woh", "wo", "mera", "meri", "mere", "tera", "teri", "tere",
        "aap", "tum", "hum", "batao", "samjhao", "samajh", "theek", "achha", "accha", "acha",
        "suno", "ruko", "bas", "karo", "karna", "kare", "karein", "chahiye", "hoga", "hogi",
        "pehle", "iska", "iski", "iske", "unka", "uski", "kaam", "karta", "karti",
        "shukriya", "dhanyawad", "namaste", "namaskar", "bhai", "yaar"
    }
    words = set(re.findall(r'[a-zA-Z]+', text.lower()))
    if len(words.intersection(hinglish_markers)) >= 1:
        return "hi-IN"
    return "en-IN"

def format_for_speech_synthesis(text: str) -> str:
    """
    Refines text specifically for speech synthesis engines:
    - Strips code blocks, markdown symbols, and list bullets so speech flows naturally.
    - Expands key technical abbreviations and math notations.
    - Ensures clean punctuation for natural cadence and breathing pauses.
    """
    if not text:
        return ""
    
    t = text
    # 1. Normalize smart quotes, dashes, ellipses
    t = t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    t = t.replace("—", ", ").replace("–", ", ").replace("…", "...")
    
    # 2. Replace code fences with spoken placeholder
    t = re.sub(r'```[\s\S]*?```', 'Code snippet provided.', t)
    t = re.sub(r'`[^`]*?`', '', t)
    
    # 3. Strip markdown links [label](url) -> label
    t = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', t)
    
    # 4. Strip markdown headers (#, ##, ###) and list indicators (*, -, 1., 2.)
    t = re.sub(r'^\s*#+\s*', '', t, flags=re.MULTILINE)
    t = re.sub(r'^\s*[-*+]\s+', '', t, flags=re.MULTILINE)
    t = re.sub(r'^\s*\d+\.\s+', '', t, flags=re.MULTILINE)
    
    # 5. Strip markdown styling characters
    t = re.sub(r'[*_~>\[\]\(\)\{\}]', '', t)
    
    # 6. Expand common math expressions for speech
    t = re.sub(r'\b(\d+)\s*\^\s*2\b', r'\1 squared', t)
    t = re.sub(r'\b(\d+)\s*\^\s*3\b', r'\1 cubed', t)
    
    # 7. Expand common technical abbreviations
    t = re.sub(r'\bAI\b', 'A.I.', t)
    t = re.sub(r'\bAPI\b', 'A.P.I.', t)
    t = re.sub(r'\bAPIs\b', 'A.P.I.s', t)
    t = re.sub(r'\bUI\b', 'U.I.', t)
    t = re.sub(r'\bFastAPI\b', 'Fast A.P.I.', t)
    t = re.sub(r'\bSQL\b', 'S.Q.L.', t)
    t = re.sub(r'\be\.g\.\b', 'for example,', t, flags=re.IGNORECASE)
    t = re.sub(r'\bi\.e\.\b', 'that is,', t, flags=re.IGNORECASE)
    t = re.sub(r'\betc\.\b', 'etcetera', t, flags=re.IGNORECASE)
    t = re.sub(r'\s*&\s*', ' and ', t)
    t = re.sub(r'\s*%\s*', ' percent ', t)
    
    # 8. Collapse whitespace
    t = re.sub(r'\s+', ' ', t).strip()
    
    # 9. Clean punctuation for sentence end
    if t and t[-1] not in ('.', '!', '?'):
        t += '.'
        
    return t

async def synthesize_sarvam_audio(
    text: str, 
    speaker: Optional[str] = None, 
    language_code: Optional[str] = None
) -> Optional[str]:
    """
    Synthesizes studio-quality neural MP3 audio using Sarvam AI Bulbul model.
    Dynamically routes between hi-IN (Hindi / Hinglish) and en-IN (Indian English).
    Returns base64-encoded audio string, or None if unavailable/offline.
    """
    if not SARVAM_API_KEY or not text.strip():
        return None
    
    selected_speaker = (speaker or SARVAM_SPEAKER or "ishita").lower().strip()
    lang = language_code or detect_query_language(text)
    
    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "text": text[:2000],
        "speaker": selected_speaker,
        "model": SARVAM_MODEL or "bulbul:v3",
        "language_code": lang,
        "output_audio_codec": "mp3"
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(SARVAM_TTS_ENDPOINT, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                audios = data.get("audios")
                if audios and len(audios) > 0 and audios[0]:
                    return audios[0]
            else:
                print(f"[Sarvam AI TTS] Warning: API returned status {resp.status_code}: {resp.text[:150]}")
    except Exception as e:
        print(f"[Sarvam AI TTS] Audio synthesis notice: {e}")
        
    return None

async def process_voice_query(
    query: str,
    mode: str = "professional",
    session_id: Optional[str] = None,
    user: Optional[Dict[str, Any]] = None,
    custom_api_key: Optional[str] = None,
    speaker: Optional[str] = None,
    language: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    clean_query = (query or "").strip()
    if not clean_query:
        return {
            "reply": "I'm listening.",
            "audio_text": "I'm listening.",
            "audio_base64": None,
            "provider": "voice_idle",
            "mode": mode,
            "should_speak": True,
            "action": None,
            "language": "en-IN"
        }

    lang_detected = language if (language and language != "auto") else detect_query_language(clean_query)
    is_hindi = lang_detected == "hi-IN"
    normalized_q = re.sub(r'[^\w\s]', '', clean_query.lower()).strip()

    # 1. Stop / Interruption Detection
    if normalized_q in STOP_WORDS or clean_query.lower() in STOP_WORDS:
        stop_reply = "Ruk gayi." if is_hindi else "Stopped."
        return {
            "reply": stop_reply,
            "audio_text": "",
            "audio_base64": None,
            "provider": "voice_interrupt",
            "mode": mode,
            "should_speak": False,
            "action": "stop",
            "language": lang_detected
        }

    # 2. Pure Acknowledgment Detection (Speak Less, Listen More)
    if normalized_q in ACK_WORDS:
        ack_reply = "Theek hai." if is_hindi else "Got it."
        return {
            "reply": ack_reply,
            "audio_text": "",
            "audio_base64": None,
            "provider": "voice_silent_ack",
            "mode": mode,
            "should_speak": False,
            "action": "acknowledge",
            "language": lang_detected
        }

    # 3. Simple Gratitude Detection
    if normalized_q in THANKS_WORDS:
        thanks_reply = "Koi baat nahi, anytime!" if is_hindi else "Anytime!"
        audio_b64 = await synthesize_sarvam_audio(thanks_reply, speaker=speaker, language_code=lang_detected)
        return {
            "reply": thanks_reply,
            "audio_text": thanks_reply,
            "audio_base64": audio_b64,
            "provider": "sarvam_bulbul_neural" if audio_b64 else "webspeech_fallback",
            "mode": mode,
            "should_speak": True,
            "action": None,
            "language": lang_detected
        }

    # 4. Action Command Detection
    for pattern, action_name, action_reply in ACTION_PATTERNS:
        if re.search(pattern, clean_query, re.IGNORECASE):
            audio_b64 = await synthesize_sarvam_audio(action_reply, speaker=speaker, language_code="en-IN")
            return {
                "reply": action_reply,
                "audio_text": action_reply,
                "audio_base64": audio_b64,
                "provider": "sarvam_bulbul_neural" if audio_b64 else "webspeech_fallback",
                "mode": mode,
                "should_speak": True,
                "action": action_name,
                "language": "en-IN"
            }

    # 5. Extract user identity details
    user_name = None
    is_guest = True
    if user:
        login_method = user.get("login_method", "")
        raw_name = user.get("username", "").strip()
        if login_method != "guest" and raw_name and not raw_name.startswith("Guest"):
            user_name = raw_name
            is_guest = False

    # 6. Load Conversation History for Contextual Memory
    conv_history: Optional[List[Dict[str, str]]] = conversation_history
    if not conv_history and session_id and user and user.get("id"):
        try:
            past_msgs = get_messages_by_session(session_id, user_id=user["id"])
            if past_msgs:
                conv_history = [
                    {"sender": m.get("sender", "user"), "content": m.get("content", "")}
                    for m in past_msgs[-6:]
                ]
        except Exception as e:
            print(f"[May Voice Context] Notice loading history: {e}")

    # 7. Build Mode and Instruction Context
    mode_tone = {
        "professional": "ACTIVE MODE: PROFESSIONAL. Maintain articulate, clear, and structured communication with professional poise.",
        "basic": "ACTIVE MODE: BASIC. Explain intuitively and simply with clean analogies. Avoid overwhelming jargon.",
        "sarcastic": "ACTIVE MODE: SARCASTIC. Be playful, witty, and playfully sarcastic with dry humor, but always answer the query accurately."
    }.get(mode.lower(), "ACTIVE MODE: PROFESSIONAL.")

    identity_clause = (
        f"USER PROFILE: Authenticated user display name is '{user_name}'. Use this name only when natural (e.g. greeting), never repeatedly."
        if user_name else
        "USER PROFILE: Guest user. Do not invent any name. Address naturally without assuming a name."
    )

    is_simple_math_or_fact = bool(re.search(r'\b(\d+\s*[\+\-\*\/\^x]\s*\d+|squared|cubed|square root|what is \d+|capital of|who is)\b', clean_query.lower()))
    is_detailed_requested = bool(re.search(r'\b(explain in detail|step by step|in detail|detailed|vistar se|poora samjhao|breakdown)\b', clean_query.lower()))

    length_guidance = (
        "CONCISENESS CONSTRAINT: The user asked a simple factual or math question. Answer directly in 1 short phrase or sentence."
        if is_simple_math_or_fact else
        ("DEPTH CONSTRAINT: The user requested a detailed/step-by-step explanation. Provide a thorough, comprehensive spoken breakdown without artificially truncating it."
         if is_detailed_requested else
         "CADENCE CONSTRAINT: Provide a direct, natural spoken response in 1 to 3 clear sentences.")
    )

    augmented_system_prompt = (
        f"{BASE_SYSTEM_INSTRUCTION}\n\n"
        f"{MAY_CORE_SYSTEM_PROMPT}\n\n"
        f"{mode_tone}\n"
        f"{identity_clause}\n"
        f"{length_guidance}\n"
        f"DETECTED USER LANGUAGE: {lang_detected} ({'Natural Indian Hinglish / Hindi' if is_hindi else 'Natural Indian English'}). Match this language in your response."
    )

    augmented_user_prompt = f"[SPOKEN VOICE QUERY from user]: {clean_query}"

    # 8. Generate AI Response
    logger.info(f"[May Diagnostics] (1) User Message: {clean_query}")
    try:
        raw_reply = await generate_ai_response(
            prompt=clean_query,
            mode="may",
            custom_api_key=custom_api_key,
            conversation_history=conv_history,
            custom_system_instruction=augmented_system_prompt
        )
        content_text = getattr(raw_reply, "content", str(raw_reply))
        provider_name = getattr(raw_reply, "provider", "unknown")
        logger.info(f"[May Diagnostics] (2) Provider: {provider_name} | Raw text preview: {content_text[:80]}...")
        clean_reply = clean_ai_response(content_text)
    except Exception as e:
        logger.warning(f"[May Voice] Generation exception: {e}")
        clean_reply = "Kuch technical issue aa gaya hai, par main yahi hoon. Dobara poochiye!" if is_hindi else "I ran into a quick connection issue, but I am right here. Please try asking again!"

    formatted_reply = format_for_speech_synthesis(clean_reply)
    logger.info(f"[May Diagnostics] (3) Selected Spoken Output: {formatted_reply}")

    # 9. Save to Session History if active session exists
    if session_id and user and user.get("id"):
        try:
            save_message(session_id, "user", clean_query, mode=mode)
            save_message(session_id, "assistant", formatted_reply, mode=mode)
        except Exception as e:
            print(f"[May Voice Session Persistence] Notice: {e}")

    # 10. Synthesize Studio Neural Audio via Sarvam AI Bulbul
    audio_base64 = await synthesize_sarvam_audio(
        formatted_reply, 
        speaker=speaker, 
        language_code=lang_detected
    )
    provider_used = "sarvam_bulbul_neural" if audio_base64 else "webspeech_fallback"

    return {
        "reply": formatted_reply,
        "audio_text": formatted_reply,
        "audio_base64": audio_base64,
        "provider": provider_used,
        "mode": mode,
        "should_speak": True,
        "action": None,
        "language": lang_detected
    }
