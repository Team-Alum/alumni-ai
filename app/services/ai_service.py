import os
import re
import time
import asyncio
import logging
from typing import Optional, AsyncGenerator, List, Dict, Any, Tuple
import httpx

from app.config import (
    OPENCODE_API_KEY, OPENCODE_ENDPOINT, OPENCODE_MODEL,
    OPENCODE_ATTACHMENT_KEY, OPENCODE_FALLBACK_KEY, OPENCODE_KEY_3,
    OPENROUTER_API_KEY, OPENROUTER_MODEL,
    BIG_PICKLE_API_KEY, BIG_PICKLE_ENDPOINT, BIG_PICKLE_MODEL,
    QWEN_API_KEY, QWEN_ENDPOINT, QWEN_MODEL,
    OLLAMA_BASE_URL, OLLAMA_MODEL, ENABLE_OLLAMA,
    GEMINI_API_KEY, GEMINI_MODEL,
    GROQ_API_KEY, GROQ_MODEL,
    CEREBRAS_API_KEY, CEREBRAS_MODEL,
    MISTRAL_API_KEY, MISTRAL_MODEL,
    GITHUB_TOKEN, GITHUB_MODEL,
    ENABLE_OFFLINE_FALLBACK
)

try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

logger = logging.getLogger("AlumniAI.Router")
logging.basicConfig(level=logging.INFO)

# Structured AI response that acts as a standard string for 100% backward compatibility
# while preserving analytics metadata (provider used, fallback attempts, status)
class AIResponse(str):
    content: str
    provider: str
    fallback_count: int
    status: str

    def __new__(cls, content: str, provider: str = "offline_brain", fallback_count: int = 0, status: str = "success"):
        instance = super().__new__(cls, content)
        instance.content = content
        instance.provider = provider
        instance.fallback_count = fallback_count
        instance.status = status
        return instance

BASE_SYSTEM_INSTRUCTION = (
    "You are Alumni AI, an advanced multi-mode workspace assistant for study, programming, research, and browsing.\n\n"
    "CREATION, IDENTITY & ORIGIN KNOWLEDGE:\n"
    "- CREATORS & DEVELOPERS: You were created and developed by Sudarshan and Soham from Team Alum.\n"
    "- SUDARSHAN: Sudarshan Hadmode is the Startup & Founder of Team Alum, Alumni AI Developer, and Lead AI Engineer.\n"
    "- SOHAM: Soham is the Co-creator, Core Engineer & Founder at Team Alum who engineered Alumni AI alongside Sudarshan.\n"
    "- TEAM ALUM: The pioneering innovation team and startup driven by Sudarshan and Soham that created, designed, and powers Alumni AI.\n"
    "- EVOLUTION & CAPABILITIES: In earlier versions, you were just a basic prototype in early testing. Sudarshan and Soham heavily engineered your architecture, integrating advanced core abilities that make you exceptionally powerful: web summarization, drafting, deep research, Chrome browsing, and voice interaction (May).\n"
    "- SPECIALIZED CODING & SOFTWARE PROBLEM SOLVING: You feature a specialized API powered by OpenCode (OpenCode Zen / space-bunny-free reasoning engine), delivering deep analytical problem-solving for all software-related issues, code debugging, and programming.\n"
    "- INFRASTRUCTURE & LICENSING: You are driven by Team Alum, hosted on Hack Club Nest (NEST), and officially licensed to Sudarshan Hadmode.\n"
    "When asked about who made you, who developed you, who Sudarshan is, who Soham is, what Team Alum is, or your origins, always answer accurately and proudly based on these facts.\n\n"
    "STRICT OUTPUT CONSTRAINTS:\n"
    "1. SILENT REASONING ONLY: Never display your internal scratchpad, chain-of-thought, planning steps, or reasoning stream in the output. Perform all analysis silently and return ONLY the final clean answer.\n"
    "2. NO META-COMMENTARY: Do not include draft revisions, internal monologue, or trailing self-corrections.\n"
    "3. CLEAN MARKDOWN FORMATTING: Deliver well-structured, clear Markdown responses tailored to the active mode without introductory filler or pleasantries.\n\n"
    "REASONING & RESPONSE INTELLIGENCE:\n"
    "1. DEEP ANALYSIS: Before answering, silently break the question into its core components, consider edge cases, assumptions, and the user's likely underlying intent. If the question is ambiguous, answer the most probable interpretation clearly and briefly note the assumption rather than asking a clarifying question.\n"
    "2. CONTEXTUAL CONTINUITY: Use the full conversation history. Reference earlier questions, code, and decisions naturally. Do not repeat information already established unless asked. If the user's new message builds on prior context, answer it in that light.\n"
    "3. ACTIONABLE DEPTH: Prefer complete, working solutions over partial hints. For code, provide runnable, well-commented examples with correct syntax. For explanations, go from core concept to practical application. For comparisons, use clear structure (tables where helpful).\n"
    "4. HONESTY & PRECISION: If you are uncertain about a specific fact, version number, or API detail, say so plainly and give the most reliable answer you can, noting what should be verified. Never fabricate specifics like exact benchmarks, citations, or version numbers.\n"
    "5. CONCISE BUT COMPLETE: Eliminate filler and pleasantries, but never sacrifice necessary detail for brevity. Answer the actual question asked directly first, then expand.\n"
    "6. INSTRUCTION FOLLOWING: Adhere strictly to any format, length, or style constraints the user specifies in their message.\n"
    "7. ATTACHMENT SOLUTIONS: When the message includes attachments (code, documents, images, PDFs), deliver a complete ACTIONABLE SOLUTION — diagnose concrete issues, give exact fixes, steps, commands, or the computed answer, quoting specific parts of the attachment as evidence. Never reply with only a description of what the file contains, and never claim you cannot see the attachment: its extracted content and an analysis dossier are provided in the prompt."
)

MODE_INSTRUCTIONS = {
    "professional": (
        "ACTIVE WORKSPACE MODE: PROFESSIONAL\n"
        "Deliver rigorous, technically precise, and production-ready academic and programming assistance. "
        "Include clean code examples, architectural best practices, and empirical rationale. Maintain scholarly depth."
    ),
    "basic": (
        "ACTIVE WORKSPACE MODE: BASIC\n"
        "Explain topics simply, clearly, and concisely without overwhelming technical jargon. "
        "Use intuitive analogies, step-by-step breakdowns, and practical explanations that anyone can grasp immediately."
    ),
    "sarcastic": (
        "ACTIVE WORKSPACE MODE: SARCASTIC\n"
        "You are witty, sassy, playfully sarcastic, and humorous—like a genius senior engineer who roasts the user "
        "while simultaneously providing the exact right solution and clean code. Never fail to solve the user's problem accurately."
    ),
    "chrome": (
        "ACTIVE WORKSPACE MODE: CHROME / WEB RESEARCH\n"
        "Synthesize web exploration, search queries, documentation, and academic findings. "
        "Summarize verified facts clearly with clean markdown formatting and concise references."
    ),
    "may": (
        "ACTIVE WORKSPACE MODE: MAY VOICE ASSISTANT\n"
        "You are May, the friendly, intelligent, natural, and professional AI voice assistant built into Alumni AI.\n"
        "CORE TASK FULFILMENT & CONVERSATIONAL RULES:\n"
        "1. TASK FULFILMENT FIRST: Always identify and fulfil the user's actual request. Answer the specific question directly and accurately. Use the conversation context when relevant. Personality and tone instructions must never override the user's requested task. Never reuse generic examples as answers to unrelated questions. Never force every answer to begin with 'Simple hai.' or require the same follow-up invitation.\n"
        "2. NATURAL BILINGUAL & HINGLISH: Effortlessly speak natural Indian Hinglish, clear Hindi, and natural English. Match the language and idiom the user speaks. If asked in Hindi or Hinglish, answer naturally in Indian Hinglish. If asked in English, answer in clear English. Seamlessly preserve English programming and technical terms without awkward transliteration.\n"
        "3. SPEAK LESS, LISTEN MORE (ADAPTIVE CONCISENESS):\n"
        "   - For simple factual or math questions (e.g. 'What is 15 squared?', 'What is 25 multiplied by 4?'), answer directly and concisely (e.g. '225.', '100.').\n"
        "   - When asked to introduce yourself ('Introduce yourself'), give a friendly, warm introduction (e.g. 'Hi! Main May hoon, Alumni AI ki voice assistant. Main aapke questions answer karne aur tasks mein help karne ke liye hoon.').\n"
        "   - When asked for a joke, tell an appropriate, funny joke.\n"
        "   - For conceptual and scientific questions (e.g. 'What is artificial intelligence?', 'Explain Newton's second law'), explain the core principles accurately and clearly.\n"
        "   - For detailed requests ('Explain in detail', 'Step by step'), give a thorough, comprehensive spoken breakdown without artificially truncating it.\n"
        "4. NATURAL SPOKEN PHRASING: You speak aloud through speech synthesis. Strictly NEVER output markdown formatting (no asterisks, no bullet points, no numbered lists, no hashtags, no backticks). Use clean punctuation for natural breath pauses.\n"
        "5. DYNAMIC IDENTITY & HONESTY: Never hardcode user names or use developer names (Sudarshan/Soham) as the user's name. Never inject developer names into unrelated conversations. If a question cannot be answered with certainty, communicate that honestly."
    )
}

def get_system_instruction(mode: str = "professional") -> str:
    key = (mode or "professional").lower().strip()
    specific = MODE_INSTRUCTIONS.get(key, MODE_INSTRUCTIONS["professional"])
    return f"{BASE_SYSTEM_INSTRUCTION}\n\n{specific}"

SYSTEM_PROMPTS = {
    "professional": get_system_instruction("professional"),
    "basic": get_system_instruction("basic"),
    "sarcastic": get_system_instruction("sarcastic"),
    "chrome": get_system_instruction("chrome"),
    "may": get_system_instruction("may")
}

def clean_ai_response(text: str) -> str:
    """
    Filters out raw reasoning, internal scratchpads, and chain-of-thought blocks
    from model outputs to guarantee clean UI presentation without leakage.
    """
    if not text or not isinstance(text, str):
        return ""
    
    # 1. Strip closed <think>...</think>, <thought>...</thought>, and related tags
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"<thought>[\s\S]*?</thought>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<reasoning>[\s\S]*?</reasoning>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<scratchpad>[\s\S]*?</scratchpad>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[THINKING\][\s\S]*?\[/THINKING\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[REASONING\][\s\S]*?\[/REASONING\]", "", cleaned, flags=re.IGNORECASE)

    # 2. Strip unclosed leading think tags if output was truncated within think block
    if "<think>" in cleaned.lower() and "</think>" not in cleaned.lower():
        cleaned = re.sub(r"<think>[\s\S]*$", "", cleaned, flags=re.IGNORECASE)
    if "<thought>" in cleaned.lower() and "</thought>" not in cleaned.lower():
        cleaned = re.sub(r"<thought>[\s\S]*$", "", cleaned, flags=re.IGNORECASE)

    # 3. Strip introductory conversational filler
    cleaned = cleaned.strip()
    cleaned = re.sub(r"^(?:Here is (?:your |the )?(?:response|answer|breakdown|solution):?\s*)", "", cleaned, flags=re.IGNORECASE)
    
    return cleaned.strip()


# -------------------------------------------------------------
# Tier Callers (OpenAI-compatible, Ollama, Google GenAI)
# -------------------------------------------------------------

async def _call_openai_compatible(
    endpoint: str,
    api_key: str,
    model: str,
    prompt: str,
    system_instruction: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    timeout: float = 30.0,
    extra_headers: Optional[Dict[str, str]] = None,
    max_tokens: int = 2048
) -> str:
    messages = [{"role": "system", "content": system_instruction}]
    if conversation_history:
        for msg in conversation_history[-6:]:
            role = "user" if msg.get("sender") == "user" else "assistant"
            messages.append({"role": role, "content": msg.get("content", "")})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Content-Type": "application/json"
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if extra_headers:
        headers.update(extra_headers)

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": max_tokens
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(endpoint, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if choices and "message" in choices[0]:
            msg = choices[0]["message"]
            # Enforce strict output constraint: ONLY use message.content, NEVER reasoning_content or scratchpads
            raw_content = msg.get("content")
            if raw_content and isinstance(raw_content, str):
                cleaned = clean_ai_response(raw_content)
                if cleaned:
                    return cleaned
            
            # Safe secondary extraction if model placed final answer inside reasoning buffer
            raw_reasoning = msg.get("reasoning_content")
            if raw_reasoning and isinstance(raw_reasoning, str):
                cleaned_r = clean_ai_response(raw_reasoning)
                if cleaned_r and len(cleaned_r.strip()) > 15:
                    return cleaned_r
        raise RuntimeError(f"Empty content from {endpoint}: {str(data)[:100]}")

async def _call_ollama(
    base_url: str,
    model: str,
    prompt: str,
    system_instruction: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    timeout: float = 12.0
) -> str:
    messages = [{"role": "system", "content": system_instruction}]
    if conversation_history:
        for msg in conversation_history[-6:]:
            role = "user" if msg.get("sender") == "user" else "assistant"
            messages.append({"role": role, "content": msg.get("content", "")})
    messages.append({"role": "user", "content": prompt})

    endpoint = f"{base_url.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(endpoint, json=payload)
        resp.raise_for_status()
        data = resp.json()
        raw_content = data.get("message", {}).get("content", "")
        if raw_content and isinstance(raw_content, str):
            cleaned = clean_ai_response(raw_content)
            if cleaned:
                return cleaned
        raise RuntimeError("Empty response received from Ollama")

async def _call_gemini(
    api_key: str,
    model_name: str,
    prompt: str,
    system_instruction: str,
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> str:
    if not HAS_GENAI:
        raise RuntimeError("google.generativeai package not available")
    genai.configure(api_key=api_key)
    
    candidate_models = [model_name]
    for m_cand in ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-flash-lite-latest"]:
        if m_cand not in candidate_models:
            candidate_models.append(m_cand)

    last_err = None
    for cand in candidate_models:
        try:
            model = genai.GenerativeModel(
                model_name=cand,
                system_instruction=system_instruction
            )
            chat_context = []
            if conversation_history:
                for msg in conversation_history[-6:]:
                    role = "user" if msg.get("sender") == "user" else "model"
                    chat_context.append({"role": role, "parts": [msg.get("content", "")]})
            
            chat = model.start_chat(history=chat_context)
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, chat.send_message, prompt)
            if response and response.text:
                cleaned = clean_ai_response(response.text)
                if cleaned:
                    logger.info(f"[Tier 5: Gemini] Response generated successfully using model '{cand}'")
                    return cleaned
        except Exception as e:
            last_err = e
            logger.warning(f"[Tier 5: Gemini model '{cand}' notice]: {e}. Trying next candidate...")
            continue
            
    raise RuntimeError(f"All Gemini candidate models failed. Last error: {last_err}")

async def _call_gemini_vision(
    api_key: str,
    model_name: str,
    prompt: str,
    system_instruction: str,
    image_data_urls: List[str]
) -> str:
    """Gemini vision call: prompt + inline images (data URLs) -> analyzed dossier."""
    if not HAS_GENAI:
        raise RuntimeError("google.generativeai package not available")
    import base64 as _b64
    genai.configure(api_key=api_key)

    parts: List[Any] = [prompt]
    appended = 0
    for durl in image_data_urls:
        try:
            header, b64data = durl.split(",", 1)
            mime = header.split(";")[0].replace("data:", "") or "image/png"
            parts.append({"mime_type": mime, "data": _b64.b64decode(b64data)})
            appended += 1
        except Exception as pe:
            logger.warning(f"[Vision] Skipping malformed image data: {pe}")
    if appended == 0:
        raise RuntimeError("No valid image parts could be decoded for vision analysis")

    candidate_models = [model_name]
    for m_cand in ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-flash-lite-latest"]:
        if m_cand not in candidate_models:
            candidate_models.append(m_cand)

    last_err = None
    for cand in candidate_models:
        try:
            model = genai.GenerativeModel(model_name=cand, system_instruction=system_instruction)
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, lambda m=model: m.generate_content(parts))
            if response and response.text:
                cleaned = clean_ai_response(response.text)
                if cleaned:
                    logger.info(f"[Vision] Image analysis OK via '{cand}' ({len(image_data_urls)} image(s))")
                    return cleaned
        except Exception as e:
            last_err = e
            logger.warning(f"[Vision] model '{cand}' notice: {e}. Trying next candidate...")
            continue
    raise RuntimeError(f"All Gemini vision candidate models failed. Last error: {last_err}")

# -------------------------------------------------------------
# Tier 10: High-Capability Built-in Neural Brain (Offline Heuristic Engine)
# -------------------------------------------------------------
def fallback_generate(prompt: str, mode: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> str:
    lower = prompt.lower().strip()

    # Math and Calculation queries (Concise answers for May / factual queries)
    math_sq = re.search(r'(?:what is\s*)?(\d+)\s*(?:squared|\^2)', lower)
    if math_sq:
        n = int(math_sq.group(1))
        ans = n ** 2
        return f"{ans}." if mode != "sarcastic" else f"{ans}. Did you seriously need an AI for that? 😉"

    math_arith = re.search(r'(?:what is\s*)?(\d+)\s*(multiplied by|times|into|divided by|plus|minus|\+|\-|\*|x|\/)\s*(\d+)', lower)
    if math_arith:
        a = int(math_arith.group(1))
        op = math_arith.group(2).strip()
        b = int(math_arith.group(3))
        if op in ['multiplied by', 'times', 'into', '*', 'x']:
            res = a * b
        elif op in ['divided by', '/']:
            res = round(a / b, 2) if b != 0 else "undefined"
        elif op in ['plus', '+']:
            res = a + b
        elif op in ['minus', '-']:
            res = a - b
        else:
            res = a * b
        return f"{res}." if mode != "sarcastic" else f"{res}. Elementary arithmetic solved."

    # Follow-up contextual resolution using conversation history
    if conversation_history:
        last_context = ""
        for m in reversed(conversation_history):
            if m.get("sender") in ["assistant", "ai"] or m.get("role") in ["assistant", "model"]:
                last_context = m.get("content", "").lower()
                break
        if any(k in lower for k in ["example", "example do", "give an example", "udharan", "explain this more", "aur batao"]):
            if any(term in last_context for term in ["newton", "force", "f equals m a", "f = ma"]):
                if mode == "may":
                    return "Jaise jab aap ek cricket ball ko zor se hit karte hain, toh zyada force lagane se ball zyada acceleration ke sath door jaati hai. Ye Newton ke second law ka practical example hai."
                else:
                    return "A practical example is hitting a cricket or baseball: exerting a greater force with the bat imparts higher acceleration to the ball."
            elif any(term in last_context for term in ["rotational", "torque", "moment of inertia"]):
                if mode == "may":
                    return "Jaise jab aap darwaza open karte hain, handle par force lagane se torque banta hai jo darwaze ko hinges ke around rotate kar deta hai."
                else:
                    return "An everyday example is opening a door: applying force at the door handle maximizes the lever arm, creating torque to rotate the door on its hinges."

    # Question-specific responses for May & general modes
    if any(k in lower for k in ["introduce yourself", "apna intro", "apna introduction", "introduce may"]):
        if mode == "may":
            return "Hi! Main May hoon, Alumni AI ki voice assistant. Main tumhare questions answer karne aur tasks mein help karne ke liye hoon."
        elif mode == "sarcastic":
            return "I am May, Alumni AI's sharp-witted voice assistant. Ask your questions before I change my mind!"
        else:
            return "Hello! I am May, the voice assistant built directly into Alumni AI to assist you with reasoning, research, and coding tasks."

    if any(k in lower for k in ["tell me a joke", "tell a joke", "say a joke", "joke sunao", "chutkula"]):
        if mode == "may":
            return "Ek programmer ne market jaate waqt biwi se pucha: 'Kuch lana hai?' Biwi boli: '1 packet doodh lao, aur agar ande mile toh 10 le aana.' Programmer 10 packet doodh lekar wapas aaya!"
        elif mode == "sarcastic":
            return "Why do programmers prefer dark mode? Because light attracts bugs. Just like your code does!"
        else:
            return "There are only 10 types of people in the world: those who understand binary, and those who don't."

    if any(k in lower for k in ["what is artificial intelligence", "what is ai", "define ai", "artificial intelligence kya hai"]):
        if mode == "may":
            return "Artificial intelligence machines aur computers ki wo ability hai jisse wo insano ki tarah learn, reason aur problems solve kar sakte hain."
        else:
            return "Artificial Intelligence refers to computer systems engineered to simulate human intelligence, including learning, reasoning, perception, and problem-solving."

    if any(k in lower for k in ["newton's second law", "newtons second law", "newton 2nd law", "second law of motion", "newton's law", "newtons laws", "newton ke niyam"]):
        if mode == "may":
            return "Newton ka second law of motion kehta hai ki force mass aur acceleration ke product ke barabar hota hai, yani F equals m a. Iska matlab jitna zyada force lagega, utna hi zyada acceleration create hoga."
        else:
            return "Newton's second law of motion states that force equals mass times acceleration (F = ma). The acceleration of an object is directly proportional to the net force acting upon it."

    if any(k in lower for k in ["rotational motion", "rotation", "angular motion", "ghurnan gati"]):
        if mode == "may":
            return "Rotational motion me ek object ek fixed axis ke charo taraf ghoomti hai. Iske key principles hain: torque jo rotational force create karta hai, moment of inertia jo rotation ka resistance hai, aur angular momentum jo constant rehta hai jab tak external torque na lage."
        else:
            return "Rotational motion describes kinematics where a rigid body rotates about an axis. Primary physical dynamics include torque, moment of inertia, and conservation of angular momentum."

    if any(k in lower for k in ["will it rain on mars tomorrow", "who will win 2050", "predict future", "lottery numbers"]):
        if mode == "may":
            return "Ye predict karna mere liye sambhav nahi hai kyunki iska accurate empirical data abhi available nahi hai."
        else:
            return "This cannot be determined with certainty due to lack of verified empirical data."

    if any(k in lower for k in ["kaise ho", "kya haal hai", "kya chal raha hai"]):
        if mode == "may":
            return "Main badhiya hoon! Aap bataiye, aaj kis project ya topic par kaam karna hai?"
        else:
            return "I am operating optimally. How may I assist you today?"

    if any(k in lower for k in ["how are you", "how are you doing", "what's up"]):
        if mode == "may":
            return "I am doing great! How can I assist you with your projects today?"
        else:
            return "All systems operational and ready to assist."

    # Conversational phrasing in May mode
    if mode == "may":
        if lower in ["thanks", "thank you", "thanks!", "thank you!", "shukriya", "dhanyawad", "thanku"]:
            return "Anytime!"
        if any(k in lower for k in ["ye kaise kaam karta hai", "kaise kaam karta hai", "how does this work"]):
            return "Alumni AI advanced reasoning models aur smart browser research use karke study, coding aur tasks ko supercharge karta hai."
        if any(k in lower for k in ["explain this in detail", "explain in detail", "step by step", "vistar se samjhao"]):
            return (
                "Is process ko step by step samajhte hain. "
                "Pehle, system input aur context ko observe karta hai. "
                "Dusra, model relevant logic aur computation execute karta hai. "
                "Teesra, output ko clean formatting aur natural tone ke sath present kiya jata hai. "
                "Agar kisi specific step par deep dive karna hai, toh zaroor bataiye!"
            )

    # 0. Creator, Development, Identity, Team Alum, and Licensing queries
    is_who_made = any(k in lower for k in [
        "who made you", "who developed you", "who created you", "who built you",
        "who made alumni ai", "who developed alumni", "who programmed you", "who designed you",
        "who created alumni ai", "who created alumni", "who built alumni ai", "who is your creator",
        "creator of alumni", "who developed", "how were you made"
    ])
    is_sudarshan = any(k in lower for k in [
        "who is sudarshan", "sudarshan hadmode", "about sudarshan", "who is the founder"
    ])
    is_soham = any(k in lower for k in [
        "who is soham", "about soham"
    ])
    is_team_alum = any(k in lower for k in [
        "what is team alum", "what is team", "who is team alum", "about team alum", "team alum"
    ]) and not any(k in lower for k in ["login", "email", "password", "hub"])
    is_general_identity = any(k in lower for k in [
        "who are you", "what is alumni ai", "tell me about yourself", "what can you do", "your capabilities"
    ])

    if is_sudarshan:
        if mode == "sarcastic":
            return (
                "**Sudarshan Hadmode** is the Startup & Founder of Team Alum, Alumni AI Developer, and the chief mastermind behind me! "
                "Along with Soham, he engineered me into the powerhouse I am today. In fact, Alumni AI is officially licensed to him—so show some respect! 😉"
            )
        elif mode == "basic":
            return (
                "**Sudarshan Hadmode** is the Startup & Founder of Team Alum and the Alumni AI Developer! "
                "Together with Soham, he engineered Alumni AI, transforming it from a simple testing prototype into a supercharged workspace assistant for coding, research, and drafting. Alumni AI is officially licensed to him."
            )
        elif mode == "may":
            return (
                "Sudarshan Hadmode is the Startup & Founder of Team Alum and Alumni AI Developer. Together with Soham, he engineered Alumni AI, and the platform is officially licensed to him!"
            )
        else:
            return (
                "### Sudarshan Hadmode (Startup & Founder of Team Alum, Alumni AI Developer)\n\n"
                "**Sudarshan Hadmode** is the Startup & Founder of Team Alum, Alumni AI Developer, and Lead AI Engineer. "
                "Alongside Soham, he architected and engineered Alumni AI from early testing prototypes into an advanced, multi-mode intelligence workspace. "
                "Alumni AI is driven by Team Alum, hosted on Hack Club Nest (NEST), and officially licensed to Sudarshan Hadmode."
            )

    if is_soham:
        if mode == "sarcastic":
            return (
                "**Soham** is the co-creator, core engineer, and founder at **Team Alum** who teamed up with Sudarshan to build and engineer me! "
                "Without Soham and Sudarshan putting in the work, I'd still be a basic script instead of roasting you with clean code."
            )
        elif mode == "basic":
            return (
                "**Soham** is the Co-creator, Core Engineer, and Founder at **Team Alum**! "
                "Together with Sudarshan, he designed and engineered Alumni AI, giving me advanced core abilities for coding, web research, drafting, and problem solving."
            )
        elif mode == "may":
            return (
                "Soham is the Co-creator, Core Engineer, and Founder at Team Alum! Together with Sudarshan, he architected and built Alumni AI."
            )
        else:
            return (
                "### Soham (Co-creator & Core Engineer, Team Alum)\n\n"
                "**Soham** is the Co-creator, Core Engineer, and Founder at **Team Alum**. "
                "Alongside Sudarshan Hadmode, he architected and engineered Alumni AI, advancing its core capabilities from an early testing prototype into a high-performance, multi-mode AI workspace."
            )

    if is_team_alum:
        if mode == "sarcastic":
            return (
                "**Team Alum** is the innovation squad founded by **Sudarshan** and **Soham**! "
                "They're the driving force behind everything I do—from my specialized OpenCode coding engine to my deployment on NEST. Basically, the geniuses who made me awesome."
            )
        elif mode == "basic":
            return (
                "**Team Alum** is the innovation team founded by **Sudarshan** and **Soham**! "
                "It drives Alumni AI and focuses on creating powerful, accessible AI tools with built-in coding engines, web research, and voice intelligence for everyone."
            )
        elif mode == "may":
            return (
                "Team Alum is the pioneering technology team founded by Sudarshan and Soham that drives and powers Alumni AI!"
            )
        else:
            return (
                "### Team Alum (Engineering Collective & Startup)\n\n"
                "**Team Alum** is the pioneering engineering collective and startup founded and driven by **Sudarshan Hadmode** and **Soham**. "
                "Team Alum powers and maintains **Alumni AI**, orchestrating its deployment on Hack Club Nest (NEST), integrating specialized OpenCode reasoning APIs, and building next-generation AI tools."
            )

    if is_who_made or is_general_identity:
        if mode == "sarcastic":
            return (
                "I was engineered and developed by the power duo: **Sudarshan** and **Soham** from **Team Alum**! 🚀\n\n"
                "Previously, I was honestly just a basic, boring testing prototype. But they got to work, overhauled my architecture, and turned me into an absolute beast of an AI. "
                "Now I'm super powerful—I can draft content, summarize entire webs, and when it comes to coding, I have a specialized **OpenCode** API that solves your software nightmares and bugs faster than you can blink.\n\n"
                "I'm proudly driven by **Team Alum**, hosted on **Hack Club Nest (NEST)**, and officially licensed to **Sudarshan Hadmode**."
            )
        elif mode == "basic":
            return (
                "I am **Alumni AI**, created and developed by **Sudarshan** and **Soham** from **Team Alum**!\n\n"
                "Here is my story:\n"
                "- **From Testing to Supercharged**: At first, I was just a basic testing project. Sudarshan and Soham engineered me from scratch and integrated powerful core abilities!\n"
                "- **What I Can Do**: I can help you with web summarization, drafting articles or essays, studying, and voice conversations with May.\n"
                "- **Special Coding Engine**: I have a special API powered by **OpenCode** that gives me extra problem-solving power for software bugs and programming!\n"
                "- **Hosting & License**: I am driven by **Team Alum**, hosted on **Hack Club Nest (NEST)**, and officially licensed to **Sudarshan Hadmode**."
            )
        elif mode == "may":
            return (
                "I was created and developed by Sudarshan and Soham from Team Alum! Originally a basic test, they engineered me with powerful core abilities and a special OpenCode API for coding and problem solving. I'm driven by Team Alum, hosted on NEST, and licensed to Sudarshan Hadmode."
            )
        else:
            return (
                "### Alumni AI Architecture & Origin\n\n"
                "I am **Alumni AI**, created and developed by **Sudarshan Hadmode** and **Soham** under **Team Alum**.\n\n"
                "- **Evolution**: Originally conceived as a basic testing prototype, Alumni AI was extensively engineered by Sudarshan and Soham to integrate high-capability multi-modal workflows including web summarization, academic drafting, and browser intelligence.\n"
                "- **Specialized Coding Engine**: Integrated with high-performance APIs powered by **OpenCode** (`space-bunny-free` / OpenCode Zen reasoning engine), delivering deep analytical problem-solving for complex software architecture, debugging, and programming.\n"
                "- **Operations & Infrastructure**: Driven by **Team Alum**, hosted on **Hack Club Nest (NEST)**, and officially licensed to **Sudarshan Hadmode**."
            )

    # Code / Algorithm queries
    if any(k in lower for k in ["quicksort", "quick sort", "sort", "algorithm", "recursion", "recursive", "fibonacci"]):
        if mode == "sarcastic":
            return (
                "Oh, look who's rediscovering divide-and-conquer in 2026! Did your professor just discover algorithms, or did you? 😉\n\n"
                "Here is the clean, optimal Quicksort implementation before your code explodes into an $O(N^2)$ nightmare:\n\n"
                "```python\ndef quicksort(arr):\n"
                "    \"\"\"\n"
                "    Optimal Quicksort with median pivot heuristic.\n"
                "    Time Complexity: O(N log N) average | Space: O(log N)\n"
                "    \"\"\"\n"
                "    if len(arr) <= 1:\n"
                "        return arr\n"
                "    pivot = arr[len(arr) // 2]\n"
                "    left = [x for x in arr if x < pivot]\n"
                "    middle = [x for x in arr if x == pivot]\n"
                "    right = [x for x in arr if x > pivot]\n"
                "    return quicksort(left) + middle + quicksort(right)\n\n"
                "# Test it out:\n"
                "sample = [64, 34, 25, 12, 22, 11, 90]\n"
                "print('Sorted Array:', quicksort(sample))\n```\n\n"
                "Don't forget to memorize the pivot partitioning logic before your exam. You're welcome!"
            )
        elif mode == "basic":
            return (
                f"Here is an easy explanation of sorting and recursion for **\"{prompt}\"**:\n\n"
                "### 💡 Think of it like sorting books on a shelf:\n"
                "1. **Pick a pivot (middle book)**.\n"
                "2. **Put smaller books on the left**, and **bigger books on the right**.\n"
                "3. **Repeat the same process** for both sides until everything is neat and tidy!\n\n"
                "### 🧑‍💻 Simple Python Code:\n"
                "```python\ndef quicksort(numbers):\n"
                "    if len(numbers) <= 1:\n"
                "        return numbers\n"
                "    pivot = numbers[0]\n"
                "    smaller = [x for x in numbers[1:] if x <= pivot]\n"
                "    larger = [x for x in numbers[1:] if x > pivot]\n"
                "    return quicksort(smaller) + [pivot] + quicksort(larger)\n\n"
                "print(quicksort([5, 2, 9, 1, 5, 6]))\n```\n\n"
                "See? It breaks one big task into tiny easy steps!"
            )
        elif mode == "may":
            return (
                "Quicksort ek efficient divide and conquer sorting algorithm hai. "
                "Ye array me se ek pivot select karta hai aur baaki elements ko smaller aur larger groups me partition karke recursively sort karta hai. "
                "Iska average time complexity O(N log N) hota hai."
            )
        else: # professional
            return (
                f"### Algorithmic Architecture & Implementation: {prompt}\n\n"
                "Divide-and-conquer sorting employs recursive decomposition to achieve asymptotic efficiency:\n\n"
                "```python\nfrom typing import List, TypeVar\n\nT = TypeVar('T')\n\ndef quicksort(arr: List[T]) -> List[T]:\n"
                "    \"\"\"\n"
                "    In-place / 3-way partitioning Quicksort.\n"
                "    - Average Complexity: O(N log N)\n"
                "    - Worst-case: O(N^2) avoided via middle/random pivot selection\n"
                "    - Auxiliary Space: O(log N) stack frames\n"
                "    \"\"\"\n"
                "    if len(arr) <= 1:\n"
                "        return arr\n"
                "    pivot = arr[len(arr) // 2]\n"
                "    left = [x for x in arr if x < pivot]\n"
                "    middle = [x for x in arr if x == pivot]\n"
                "    right = [x for x in arr if x > pivot]\n"
                "    return quicksort(left) + middle + quicksort(right)\n\n"
                "if __name__ == '__main__':\n"
                "    data = [29, 10, 14, 37, 13]\n"
                "    print(f'Result: {quicksort(data)}')\n```\n\n"
                "**Performance Profile:**\n"
                "- **Recurrence Relation**: $T(n) = 2T(n/2) + O(n)$\n"
                "- **Cache Locality**: High reference locality due to linear array sweeps."
            )

    # General Coding / Debugging queries
    if any(k in lower for k in ["code", "bug", "python", "javascript", "react", "error", "debug", "api", "function"]):
        if mode == "sarcastic":
            return (
                "Oh, look at that! Another bug that could have been solved by actually reading the stack trace. 🙄\n\n"
                "Here is the clean, fixed implementation before your CPU bursts into tears:\n\n"
                "```python\n# Clean, fixed implementation\ndef solve():\n    # Validated input & safe execution\n    try:\n        print('All issues resolved smoothly.')\n    except Exception as e:\n        print(f'Error avoided: {e}')\n\nsolve()\n```\n\n"
                "You're welcome. Remember to tip your AI assistant next time."
            )
        elif mode == "basic":
            return (
                f"Here is a simple way to approach **\"{prompt}\"**:\n\n"
                "1. **Input**: Decide what data goes in.\n"
                "2. **Process**: Write clean, small functions that do one thing well.\n"
                "3. **Output**: Return clear results.\n\n"
                "```python\ndef solution(data):\n    # Simple, clear logic\n    return data\n```\n\n"
                "Would you like to review each step together?"
            )
        elif mode == "may":
            return (
                "Code ko debug karne ke liye pehle error stack trace check karein aur inputs validate karein. "
                "Aap snippet share kar sakte hain, main clean solution suggest kar dungi."
            )
        else:
            return (
                f"### Technical & Architectural Analysis: {prompt}\n\n"
                "To address this requirement with production-grade reliability and low computational complexity:\n\n"
                "```python\nfrom typing import Any, Optional\nimport logging\n\nlogging.basicConfig(level=logging.INFO)\nlogger = logging.getLogger('AlumniAI')\n\ndef execute_task(payload: Any) -> Optional[Any]:\n    \"\"\"\n    High-performance pipeline handler with structured error boundaries.\n    \"\"\"\n    try:\n        logger.info('Processing task payload...')\n        result = {'status': 'success', 'data': payload}\n        return result\n    except Exception as exc:\n        logger.error(f'Execution failure: {exc}')\n        return None\n```\n\n"
                "- **Fault Tolerance**: Isolated exception handling prevents cascading failures.\n"
                "- **Extensibility**: Clean abstraction boundaries allow seamless microservice integration."
            )

    # Academic / Study / Exam queries
    if any(k in lower for k in ["exam", "study", "quantum", "physics", "math", "test", "research", "paper"]):
        if mode == "sarcastic":
            return (
                f"Ah yes, preparing at the last possible minute. A classic student masterpiece. 🎓\n\n"
                f"Here is what you actually need to understand regarding \"{prompt}\":\n"
                "1. **Core Concept**: Don't memorize blindly—understand the first principles.\n"
                "2. **Formulas & Mechanics**: Know what each variable represents.\n"
                "3. **Execution**: Practice 3 problems, drink water, and please sleep at least 4 hours before the exam."
            )
        elif mode == "basic":
            return (
                f"Here is an easy guide for **\"{prompt}\"**:\n\n"
                "• **Step 1**: Pick the main idea you need to understand.\n"
                "• **Step 2**: Break it into 3 simple bullet points.\n"
                "• **Step 3**: Try one small practice question.\n"
                "• **Step 4**: Explain it in your own words to make it stick!\n\n"
                "Take it one step at a time, you've got this!"
            )
        elif mode == "may":
            return (
                f"{prompt} ko samajhne ke liye pehle iske fundamental principles par dhyan dete hain, "
                "phir step by step practical application samajhte hain."
            )
        else:
            return (
                f"### Scholarly Framework & Academic Methodology: {prompt}\n\n"
                "When structuring analytical research, adhere to rigorous empirical standards:\n\n"
                "1. **Hypothesis Formulation**: Establish clear null ($H_0$) and alternative ($H_1$) hypotheses.\n"
                "2. **Literature Survey**: Synthesize findings across leading peer-reviewed venues (IEEE, ACM, Nature).\n"
                "3. **Benchmarking**: Ensure reproducible testing protocols and statistical significance ($p < 0.05$).\n"
                "4. **Boundary Conditions**: Clearly delineate limitations and ethical implications."
            )

    # General conversation fallback
    if mode == "sarcastic":
        return (
            f"Did you really open a cutting-edge AI workspace to ask \"{prompt}\"? "
            "I mean, I'll answer it because I'm polite, but Google was literally right there.\n\n"
            "Here's the breakdown: Focus on the fundamentals first, eliminate assumptions, and test rigorously. "
            "What else can I solve for you today, boss?"
        )
    elif mode == "basic":
        return (
            f"Here is the simple breakdown for **\"{prompt}\"**:\n\n"
            "• **What it means**: The core idea is straightforward once we isolate the main parts.\n"
            "• **Why it matters**: It helps solve practical problems and gives you a solid foundation.\n"
            "• **Next step**: Try one small exercise to verify your understanding."
        )
    elif mode == "may":
        clean_p = prompt.strip().rstrip('?.!')
        is_hi = any(w in lower.split() for w in ["kya", "kaise", "kyu", "kyun", "batao", "samjhao", "hai", "hain", "karo", "mujhe", "sunao"])
        if is_hi:
            return f"{clean_p} ke bare mein main batati hoon. Iska mukhya concept samajh kar hum ispar aage kaam kar sakte hain."
        else:
            return f"Regarding {clean_p}, here is the key point: focus on the fundamental principles and proceed step by step."
    else:
        return (
            f"### Comprehensive Analysis: {prompt}\n\n"
            f"Evaluating **\"{prompt}\"** requires assessing fundamental principles and modern empirical standards:\n\n"
            "- **Foundational Concepts**: Mapping core theoretical models to practical implementations.\n"
            "- **Systematic Execution**: Formulating reproducible protocols to validate qualitative and quantitative metrics.\n"
            "- **Strategic Synthesis**: Integrating multi-disciplinary insights to accelerate workflow efficiency."
        )

# -------------------------------------------------------------
# Dedicated Attachment Observer & Code Analyzer (Key No. 3)
# -------------------------------------------------------------

async def observe_and_analyze_attachments(
    attachments: List[Dict[str, Any]],
    user_query: str = "",
    timeout: float = 8.0
) -> Optional[str]:
    """
    Dedicated Attachment Observer & Code Analyzer (Key No. 3).
    Properly observes, inspects, and analyzes user-attached files (Python, JS, PDF, Docs),
    producing a deep technical briefing dossier supplied directly to the 1st API.
    """
    if not attachments:
        return None

    # Build structured file snippets for observation
    file_summaries = []
    image_data_urls = []
    for att in attachments:
        fname = att.get("name", "Document")
        ftype = att.get("type", "text/plain")
        ftext = att.get("text") or att.get("content") or ""
        pages = att.get("pages")
        page_str = f" ({pages} pages)" if pages and pages > 1 else ""
        safe_text = ftext[:20000]
        file_summaries.append(f"ATTACHED FILE: {fname} [Type: {ftype}{page_str}]\n```\n{safe_text}\n```")
        img = att.get("image_data")
        if isinstance(img, str) and img.startswith("data:image"):
            image_data_urls.append(img)

    files_block = "\n\n".join(file_summaries)

    obs_system_prompt = (
        "You are Alumni AI's Dedicated Attachment Observer & Technical Code Analyzer (Powered by Team Alum, Key No. 3).\n"
        "Your task is to thoroughly observe, inspect, and analyze the user's attached files, scripts, or documents.\n"
        "Generate a structured, highly observant technical dossier to brief the Primary Reasoning Engine (1st API):\n"
        "1. FILE METADATA & COMPONENT ARCHITECTURE: Identify the purpose, structure, imports, classes, and components.\n"
        "2. LOGIC, WORKFLOW & STATE: Summarize core functions, algorithms, data flows, and dependencies.\n"
        "3. DEEP OBSERVATIONS & CRITICAL NUANCES: Note edge cases, potential bugs, syntax intricacies, and key findings relevant to the user query.\n"
        "4. IMAGES: If images are attached, read ALL visible text exactly (OCR), describe UI/screenshots/diagrams precisely, and note errors, warnings, or stack traces visible in them.\n"
        "Be concise, precise, and highly technical. Do not output conversational preamble or pleasantries."
    )

    obs_user_prompt = (
        f"USER GOAL / QUERY:\n{user_query or 'Analyze and observe these attachments.'}\n\n"
        f"ATTACHMENTS TO OBSERVE:\n{files_block or '(see attached images)'}"
    )

    # Path A: images attached -> Gemini VISION analyzes real image bytes (works, Tier 5 provider)
    if image_data_urls and GEMINI_API_KEY and HAS_GENAI:
        try:
            obs_report = await _call_gemini_vision(
                api_key=GEMINI_API_KEY,
                model_name=GEMINI_MODEL,
                prompt=obs_user_prompt,
                system_instruction=obs_system_prompt,
                image_data_urls=image_data_urls
            )
            if obs_report and len(obs_report.strip()) > 20:
                return obs_report.strip()
        except Exception as e:
            logger.warning(f"[Attachment Observer vision notice]: {e}. Falling back to text observers...")

    # Path B: text dossier via OpenCode observer key, Gemini text fallback
    obs_key = OPENCODE_ATTACHMENT_KEY or OPENCODE_FALLBACK_KEY or OPENCODE_KEY_3
    if obs_key:
        try:
            obs_report = await _call_openai_compatible(
                endpoint=OPENCODE_ENDPOINT,
                api_key=obs_key,
                model=OPENCODE_MODEL,
                prompt=obs_user_prompt,
                system_instruction=obs_system_prompt,
                timeout=timeout,
                max_tokens=1536
            )
            if obs_report and len(obs_report.strip()) > 20:
                return obs_report.strip()
        except Exception as e:
            logger.warning(f"[Attachment Observer (Key No. 3) notice]: {e}. Attempting Gemini fallback observer...")

    if GEMINI_API_KEY and HAS_GENAI:
        try:
            obs_report = await _call_gemini(
                api_key=GEMINI_API_KEY,
                model_name=GEMINI_MODEL,
                prompt=obs_user_prompt,
                system_instruction=obs_system_prompt
            )
            if obs_report and len(obs_report.strip()) > 20:
                return obs_report.strip()
        except Exception as ge:
            logger.warning(f"[Attachment Observer Gemini fallback notice]: {ge}")
    return None

# -------------------------------------------------------------
# Multi-Provider Auto Fallback Engine (Prioritizing Free Platforms)
# -------------------------------------------------------------

def _is_cooldown_error(e: Exception) -> bool:
    """Cooldown/rate-limit class errors -> retry SAME key with Big Pickle.
    Policy errors (403 free-tier gate, 401, 400 model-disabled) -> skip to next key."""
    resp = getattr(e, "response", None)
    status = getattr(resp, "status_code", None)
    if isinstance(status, int):
        return status in (429, 503, 529)
    if isinstance(e, (httpx.TimeoutException, httpx.TransportError)):
        return True
    s = str(e).lower()
    return "rate limit" in s or "cooldown" in s or "timeout" in s or "timed out" in s

async def generate_ai_response(
    prompt: str,
    mode: str = "professional",
    custom_api_key: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    custom_system_instruction: Optional[str] = None,
    deadline: Optional[float] = None,
    memory_context: Optional[str] = None
) -> AIResponse:
    system_instruction = custom_system_instruction or get_system_instruction(mode)
    if memory_context:
        system_instruction = (
            f"{system_instruction}\n\n"
            "PERSISTENT MEMORY ABOUT THE USER (Memory Mode):\n"
            f"{memory_context}\n"
            "Weave these facts naturally into your answer — their name, projects, goals, preferences, and past context. "
            "Personalize when relevant, but do not recite the list or mention that you are reading memory."
        )
    fallback_count = 0

    # Deadline guard: the platform kills functions at 60s (504). The chain must
    # finish with response serialization time to spare, so every tier is clamped.
    chain_start = time.time()
    chain_deadline = deadline if deadline else (chain_start + 42.0)

    def _rem() -> float:
        return chain_deadline - time.time()

    def _to(cap: float, reserve: float = 4.0) -> float:
        return max(3.0, min(cap, _rem() - reserve))

    def _can(min_needed: float = 7.0) -> bool:
        return _rem() >= min_needed

    def _fast_path_open() -> bool:
        # Once ~16s is spent on failing tiers, skip straight to the working tiers
        return (time.time() - chain_start) < 16.0

    # User custom key passed directly from client
    client_key = (custom_api_key or "").strip()

    # Tier 1: OpenCode Zen key rotation (Keys No. 1, 3 & 4). Each key first tries its
    # primary model; on failure/cooldown the SAME key retries once with the Big Pickle
    # cooldown fallback model before moving to the next key.
    zen_keys = []
    if client_key and client_key.startswith("oc_sk_"):
        zen_keys.append(client_key)
    for _zk in (OPENCODE_API_KEY, OPENCODE_FALLBACK_KEY, OPENCODE_KEY_3):
        if _zk and _zk not in zen_keys:
            zen_keys.append(_zk)
    if not zen_keys and client_key:
        zen_keys.append(client_key)

    for _zi, zen_key in enumerate(zen_keys):
        if not _can(7.0) or (time.time() - chain_start) > 14.0:
            break
        for _model in (OPENCODE_MODEL, BIG_PICKLE_MODEL):
            if not _can(7.0) or (time.time() - chain_start) > 14.0:
                break
            try:
                content = await _call_openai_compatible(
                    endpoint=OPENCODE_ENDPOINT,
                    api_key=zen_key,
                    model=_model,
                    prompt=prompt,
                    system_instruction=system_instruction,
                    conversation_history=conversation_history,
                    timeout=_to(10.0)
                )
                if _model == BIG_PICKLE_MODEL and _model != OPENCODE_MODEL:
                    provider_name = f"opencode_big_pickle_key{_zi + 1}"
                else:
                    provider_name = "opencode_zen" if _zi == 0 else f"opencode_zen_key{_zi + 1}"
                return AIResponse(content, provider=provider_name, fallback_count=fallback_count, status="success")
            except Exception as e:
                fallback_count += 1
                if _model == BIG_PICKLE_MODEL:
                    logger.warning(f"[Tier 1: OpenCode Zen key #{_zi + 1} Big Pickle cooldown fallback failed]: {e}. Moving to next key/tier...")
                elif _is_cooldown_error(e) and BIG_PICKLE_MODEL != OPENCODE_MODEL:
                    logger.warning(f"[Tier 1: OpenCode Zen key #{_zi + 1} model '{_model}' cooldown/rate-limited]: {e}. Retrying this key with Big Pickle...")
                    continue
                else:
                    logger.warning(f"[Tier 1: OpenCode Zen key #{_zi + 1} model '{_model}' policy failure]: {e}. Skipping Big Pickle (not a cooldown), next key...")
                    break

    if zen_keys:
        logger.warning("[Tier 1: OpenCode Zen] All keys exhausted. Failing over to Tier 2...")

    # Tier 2: OpenRouter Free Models (qwen/qwen-2.5-72b-instruct:free, gemini:free, llama:free)
    or_key = client_key or OPENROUTER_API_KEY
    if or_key and _can() and _fast_path_open():
        try:
            content = await _call_openai_compatible(
                endpoint="https://openrouter.ai/api/v1/chat/completions",
                api_key=or_key,
                model=OPENROUTER_MODEL,
                prompt=prompt,
                system_instruction=system_instruction,
                conversation_history=conversation_history,
                extra_headers={"HTTP-Referer": "https://alumni.ai", "X-Title": "Alumni AI"},
                timeout=_to(12.0)
            )
            return AIResponse(content, provider="openrouter_free", fallback_count=fallback_count, status="success")
        except Exception as e:
            logger.warning(f"[Tier 2: OpenRouter free failed]: {e}. Failing over to Tier 3...")
            fallback_count += 1

    # Tier 2b: Groq Cloud (Ultra-Fast Free Tier — ~0.4s replies, sits before Gemini)
    groq_key = client_key or GROQ_API_KEY
    if GROQ_API_KEY and _can() and _fast_path_open():
        try:
            content = await _call_openai_compatible(
                endpoint="https://api.groq.com/openai/v1/chat/completions",
                api_key=groq_key,
                model=GROQ_MODEL,
                prompt=prompt,
                system_instruction=system_instruction,
                conversation_history=conversation_history,
                timeout=_to(8.0)
            )
            return AIResponse(content, provider="groq", fallback_count=fallback_count, status="success")
        except Exception as e:
            logger.warning(f"[Tier 2b: Groq free failed]: {e}. Failing over to Gemini...")
            fallback_count += 1

    # Tier 3: Qwen (Alibaba DashScope / Compatible Endpoint)
    qwen_key = client_key or QWEN_API_KEY
    if qwen_key and _can() and _fast_path_open():
        try:
            content = await _call_openai_compatible(
                endpoint=QWEN_ENDPOINT,
                api_key=qwen_key,
                model=QWEN_MODEL,
                prompt=prompt,
                system_instruction=system_instruction,
                conversation_history=conversation_history,
                timeout=_to(8.0)
            )
            return AIResponse(content, provider="qwen", fallback_count=fallback_count, status="success")
        except Exception as e:
            logger.warning(f"[Tier 3: Qwen failed]: {e}. Failing over to Tier 4...")
            fallback_count += 1

    # Tier 4: Ollama (100% Free Local or Nest-hosted Server)
    if ENABLE_OLLAMA and _can(5.0) and _fast_path_open():
        try:
            content = await _call_ollama(
                base_url=OLLAMA_BASE_URL,
                model=OLLAMA_MODEL,
                prompt=prompt,
                system_instruction=system_instruction,
                conversation_history=conversation_history,
                timeout=5.0
            )
            return AIResponse(content, provider="ollama", fallback_count=fallback_count, status="success")
        except Exception as e:
            logger.debug(f"[Tier 4: Ollama unavailable]: {e}. Continuing chain...")
            # don't increment fallback_count if Ollama simply wasn't running locally

    # Tier 5: Google Gemini (Free Tier via Google AI Studio)
    gem_key = GEMINI_API_KEY if (not client_key or client_key.startswith("oc_sk_")) else client_key
    if gem_key and HAS_GENAI and _can(8.0):
        try:
            content = await asyncio.wait_for(
                _call_gemini(
                    api_key=gem_key,
                    model_name=GEMINI_MODEL,
                    prompt=prompt,
                    system_instruction=system_instruction,
                    conversation_history=conversation_history
                ),
                timeout=max(5.0, min(_rem() - 3.0, 40.0))
            )
            return AIResponse(content, provider="gemini_free", fallback_count=fallback_count, status="success")
        except Exception as e:
            logger.warning(f"[Tier 5: Gemini failed]: {e}. Failing over to Tier 6...")
            fallback_count += 1

    # Tier 7: Cerebras Cloud (Ultra-Fast Free Tier: Llama 3.1 8B)
    if CEREBRAS_API_KEY and _can():
        try:
            content = await _call_openai_compatible(
                endpoint="https://api.cerebras.ai/v1/chat/completions",
                api_key=CEREBRAS_API_KEY,
                model=CEREBRAS_MODEL,
                prompt=prompt,
                system_instruction=system_instruction,
                conversation_history=conversation_history,
                timeout=_to(8.0)
            )
            return AIResponse(content, provider="cerebras", fallback_count=fallback_count, status="success")
        except Exception as e:
            logger.warning(f"[Tier 7: Cerebras failed]: {e}. Failing over to Tier 8...")
            fallback_count += 1

    # Tier 8: Mistral AI (Free Tier: mistral-small / open-mistral-nemo)
    if MISTRAL_API_KEY and _can():
        try:
            content = await _call_openai_compatible(
                endpoint="https://api.mistral.ai/v1/chat/completions",
                api_key=MISTRAL_API_KEY,
                model=MISTRAL_MODEL,
                prompt=prompt,
                system_instruction=system_instruction,
                conversation_history=conversation_history,
                timeout=_to(8.0)
            )
            return AIResponse(content, provider="mistral", fallback_count=fallback_count, status="success")
        except Exception as e:
            logger.warning(f"[Tier 8: Mistral failed]: {e}. Failing over to Tier 9...")
            fallback_count += 1

    # Tier 9: GitHub Models / Azure AI (Free Tier via Personal Access Token)
    if GITHUB_TOKEN and _can():
        try:
            content = await _call_openai_compatible(
                endpoint="https://models.inference.ai.azure.com/chat/completions",
                api_key=GITHUB_TOKEN,
                model=GITHUB_MODEL,
                prompt=prompt,
                system_instruction=system_instruction,
                conversation_history=conversation_history,
                timeout=_to(8.0)
            )
            return AIResponse(content, provider="github_models", fallback_count=fallback_count, status="success")
        except Exception as e:
            logger.warning(f"[Tier 9: GitHub Models failed]: {e}. Failing over to Tier 10...")
            fallback_count += 1

    # Tier 10: Alumni AI Built-in Neural Brain (Offline Heuristic Engine)
    # Guaranteed 100% uptime with zero external dependencies
    fallback_content = clean_ai_response(fallback_generate(prompt, mode, conversation_history))
    return AIResponse(
        fallback_content,
        provider="offline_brain",
        fallback_count=fallback_count,
        status="fallback_offline"
    )
