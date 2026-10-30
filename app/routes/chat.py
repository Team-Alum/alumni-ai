import re
import uuid
import time
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from app.models import ChatRequest, ChatResponse
from app.database import (
    save_message,
    get_messages_by_session,
    get_session_by_id_and_user,
    create_session,
    log_analytics_event,
    get_user_memories,
    add_user_memory
)
from app.services.ai_service import generate_ai_response, clean_ai_response, observe_and_analyze_attachments
from app.services.research_service import (
    gather_web_research,
    synthesize_research_with_first_api,
    generate_suggested_questions
)
from app.security import get_current_user
import json
import asyncio

router = APIRouter(prefix="/api/chat", tags=["Chat"])

@router.post("", response_model=ChatResponse)
async def handle_chat_message(payload: ChatRequest, user: dict = Depends(get_current_user)):
    clean_msg = payload.message.strip()
    if not clean_msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
        
    session_id = payload.session_id
    if session_id:
        existing = get_session_by_id_and_user(session_id, user["id"])
        if not existing:
            session_id = None # Do not allow accessing someone else's session
            
    if not session_id:
        session_id = str(uuid.uuid4())
        title = clean_msg[:35] + ("..." if len(clean_msg) > 35 else "")
        create_session(
            session_id=session_id,
            user_id=user["id"],
            title=title,
            category=payload.category or "general",
            mode=payload.mode or "professional"
        )
        
    # 1. Format & save user message with optional attachments
    import json
    raw_attachments_json = json.dumps(payload.attachments) if payload.attachments else None
    user_msg = save_message(
        session_id=session_id,
        sender="user",
        content=clean_msg,
        mode=payload.mode,
        attachments=raw_attachments_json
    )
    
    # 2. Retrieve recent history for context
    history = get_messages_by_session(session_id)
    
    start_time = time.time()
    # Absolute deadline so the AI chain always finishes inside the 60s platform limit
    response_deadline = start_time + 46.0
    sources = None
    suggested_questions = None

    # 2b. Memory Mode: inject stored facts into the AI system instruction (fast DB read, ~0ms)
    memory_used = False
    memory_context = None
    if payload.use_memory is not False:
        try:
            mem_rows = get_user_memories(user["id"])
            if mem_rows:
                memory_context = "\n".join(f"- {m['content']}" for m in mem_rows[:40])
                memory_used = True
            # Zero-latency explicit capture: "/remember X", "remember that ...", "my name is ..."
            for pat in (
                r"^\s*(?:\/remember|remember\s+that|remember\s*[:,])\s*(.+)$",
                r"\b(my name is|i am called|call me|i'?m working on|i am working on|my project is|i study|i am currently(?: a| learning)|i'm currently(?: a| learning))\b[^.!?\n]{2,220}"
            ):
                for m in re.findall(pat, clean_msg, flags=re.IGNORECASE):
                    if isinstance(m, tuple):
                        m = m[0]
                    add_user_memory(user["id"], m.strip().rstrip("."), source="auto")
        except Exception as mem_err:
            print(f"[Memory] capture/inject notice: {mem_err}")

    # Build effective prompt with file attachment context if provided
    effective_prompt = clean_msg
    if payload.attachments:
        # Step A: Key No. 3 properly observes and analyzes attachments to brief the 1st API
        obs_dossier = await observe_and_analyze_attachments(
            attachments=payload.attachments,
            user_query=clean_msg
        )

        file_contexts = []
        for att in payload.attachments:
            fname = att.get("name", "Document")
            ftext = att.get("text") or att.get("content") or ""
            pages = att.get("pages")
            page_info = f" ({pages} pages)" if pages and pages > 1 else ""
            safe_ftext = ftext[:24000]
            file_contexts.append(f"📁 [ATTACHED FILE: {fname}{page_info}]\n```\n{safe_ftext}\n```")
        
        file_banner = "\n\n".join(file_contexts)
        if obs_dossier:
            effective_prompt = (
                f"🔬 [ATTACHMENT OBSERVATION & CODE ANALYSIS DOSSIER (Key No. 3)]:\n"
                f"{obs_dossier}\n\n"
                f"{file_banner}\n\n"
                f"[USER PROMPT / TASK FOR 1ST API]:\n{clean_msg}"
            )
        else:
            effective_prompt = f"{file_banner}\n\n[USER PROMPT / TASK]:\n{clean_msg}"

    # Check if web research was requested via payload flag or prompt keyword
    is_web_research = bool(payload.web_research or clean_msg.lower().startswith("@research") or clean_msg.lower().startswith("/research"))

    if is_web_research:
        research_query = re.sub(r"^(@research|/research)\s*", "", clean_msg, flags=re.IGNORECASE).strip()
        # Step 1: Research API gathers overall web information
        research_data = await gather_web_research(query=research_query or clean_msg, depth="deep", max_results=5)
        sources = research_data.get("sources", [])
        
        # Step 2: First API analyzes & synthesizes findings
        cleaned_reply, provider_used = await synthesize_research_with_first_api(
            query=research_query or clean_msg,
            research_data=research_data,
            mode=payload.mode or "professional",
            custom_api_key=payload.custom_api_key
        )
        fallback_count = 0
        status = "success"
        # Step 3: Generate follow-up question suggestions
        suggested_questions = generate_suggested_questions(research_query or clean_msg, cleaned_reply, mode=payload.mode)
    else:
        # Standard chat pipeline
        ai_content = await generate_ai_response(
            prompt=effective_prompt,
            mode=payload.mode,
            custom_api_key=payload.custom_api_key,
            conversation_history=history,
            deadline=response_deadline,
            memory_context=memory_context
        )
        provider_used = getattr(ai_content, "provider", "offline_brain")
        fallback_count = getattr(ai_content, "fallback_count", 0)
        status = getattr(ai_content, "status", "success")
        cleaned_reply = clean_ai_response(str(ai_content))
        suggested_questions = generate_suggested_questions(clean_msg, cleaned_reply, mode=payload.mode)

    latency_ms = max(1, int((time.time() - start_time) * 1000))

    # 4. Save AI message
    ai_msg = save_message(
        session_id=session_id,
        sender="ai",
        content=cleaned_reply,
        mode=payload.mode
    )

    # 5. Record Analytics Event
    try:
        log_analytics_event(
            user_id=user["id"],
            session_id=session_id,
            prompt_chars=len(clean_msg),
            response_chars=len(cleaned_reply),
            latency_ms=latency_ms,
            provider_used=f"web_research+{provider_used}" if is_web_research else provider_used,
            fallback_count=fallback_count,
            mode=payload.mode,
            status=status
        )
    except Exception as e:
        print(f"[Analytics] Log notice: {e}")
    
    return {
        "session_id": session_id,
        "user_message": user_msg,
        "ai_message": ai_msg,
        "sources": sources,
        "suggested_questions": suggested_questions,
        "memory_used": memory_used
    }


@router.post("/stream")
async def handle_chat_message_stream(payload: ChatRequest, user: dict = Depends(get_current_user)):
    clean_msg = payload.message.strip()
    if not clean_msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    session_id = payload.session_id
    if session_id:
        existing = get_session_by_id_and_user(session_id, user["id"])
        if not existing:
            session_id = None

    if not session_id:
        session_id = str(uuid.uuid4())
        title = clean_msg[:35] + ("..." if len(clean_msg) > 35 else "")
        create_session(
            session_id=session_id,
            user_id=user["id"],
            title=title,
            category=payload.category or "general",
            mode=payload.mode or "professional"
        )

    import json as _json
    raw_attachments_json = _json.dumps(payload.attachments) if payload.attachments else None
    user_msg = save_message(
        session_id=session_id,
        sender="user",
        content=clean_msg,
        mode=payload.mode,
        attachments=raw_attachments_json
    )

    history = get_messages_by_session(session_id)
    start_time = time.time()
    response_deadline = start_time + 46.0
    sources = None
    suggested_questions = None

    memory_used = False
    memory_context = None
    if payload.use_memory is not False:
        try:
            mem_rows = get_user_memories(user["id"])
            if mem_rows:
                memory_context = "\n".join(f"- {m['content']}" for m in mem_rows[:40])
                memory_used = True
            for pat in (
                r"^\s*(?:\/remember|remember\s+that|remember\s*[:,])\s*(.+)$",
                r"\b(my name is|i am called|call me|i'?m working on|i am working on|my project is|i study|i am currently(?: a| learning)|i'm currently(?: a| learning))\b[^.!?\n]{2,220}"
            ):
                for m in re.findall(pat, clean_msg, flags=re.IGNORECASE):
                    if isinstance(m, tuple):
                        m = m[0]
                    add_user_memory(user["id"], m.strip().rstrip("."), source="auto")
        except Exception:
            pass

    effective_prompt = clean_msg
    if payload.attachments:
        try:
            obs_dossier = await observe_and_analyze_attachments(
                attachments=payload.attachments,
                user_query=clean_msg
            )
            file_contexts = []
            for att in payload.attachments:
                fname = att.get("name", "Document")
                ftext = att.get("text") or att.get("content") or ""
                pages = att.get("pages")
                page_info = f" ({pages} pages)" if pages and pages > 1 else ""
                safe_ftext = str(ftext)[:24000]
                file_contexts.append(f"[ATTACHED FILE: {fname}{page_info}]\n```\n{safe_ftext}\n```")
            file_banner = "\n\n".join(file_contexts)
            if obs_dossier:
                effective_prompt = (
                    f"[ATTACHMENT OBSERVATION & CODE ANALYSIS DOSSIER]:\n{obs_dossier}\n\n{file_banner}\n\n[USER PROMPT / TASK]:\n{clean_msg}"
                )
            else:
                effective_prompt = f"{file_banner}\n\n[USER PROMPT / TASK]:\n{clean_msg}"
        except Exception:
            pass

    is_web_research = bool(payload.web_research or clean_msg.lower().startswith("@research") or clean_msg.lower().startswith("/research"))

    async def event_generator():
        try:
            yield f"data: {_json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
            if is_web_research:
                research_query = re.sub(r"^(@research|/research)\s*", "", clean_msg, flags=re.IGNORECASE).strip()
                research_data = await gather_web_research(query=research_query or clean_msg, depth="deep", max_results=5)
                sources = research_data.get("sources", [])
                cleaned_reply, provider_used = await synthesize_research_with_first_api(
                    query=research_query or clean_msg,
                    research_data=research_data,
                    mode=payload.mode or "professional",
                    custom_api_key=payload.custom_api_key
                )
                suggested_questions = generate_suggested_questions(research_query or clean_msg, cleaned_reply, mode=payload.mode)
                # stream in chunks
                text_out = clean_ai_response(str(cleaned_reply))
                try:
                    log_analytics_event(
                        user_id=user["id"],
                        session_id=session_id,
                        prompt_chars=len(clean_msg),
                        response_chars=len(text_out),
                        latency_ms=max(1, int((time.time() - start_time) * 1000)),
                        provider_used=f"web_research+{provider_used}",
                        fallback_count=0,
                        mode=payload.mode,
                        status="success"
                    )
                except Exception as e:
                    print(f"[Analytics] Log notice: {e}")
                for i in range(0, len(text_out), 80):
                    yield f"data: {_json.dumps({'type': 'token', 'content': text_out[i:i+80]})}\n\n"
                    await asyncio.sleep(0.01)
                ai_msg = save_message(session_id=session_id, sender="ai", content=text_out, mode=payload.mode)
                yield f"data: {_json.dumps({'type': 'done', 'ai_message': ai_msg, 'sources': sources, 'suggested_questions': suggested_questions, 'memory_used': memory_used})}\n\n"
            else:
                ai_content = await generate_ai_response(
                    prompt=effective_prompt,
                    mode=payload.mode,
                    custom_api_key=payload.custom_api_key,
                    conversation_history=history,
                    deadline=response_deadline,
                    memory_context=memory_context
                )
                text_out = clean_ai_response(str(ai_content))
                try:
                    log_analytics_event(
                        user_id=user["id"],
                        session_id=session_id,
                        prompt_chars=len(clean_msg),
                        response_chars=len(text_out),
                        latency_ms=max(1, int((time.time() - start_time) * 1000)),
                        provider_used=getattr(ai_content, "provider", "offline_brain"),
                        fallback_count=getattr(ai_content, "fallback_count", 0),
                        mode=payload.mode,
                        status=getattr(ai_content, "status", "success")
                    )
                except Exception as e:
                    print(f"[Analytics] Log notice: {e}")
                for i in range(0, len(text_out), 80):
                    yield f"data: {_json.dumps({'type': 'token', 'content': text_out[i:i+80]})}\n\n"
                    await asyncio.sleep(0.01)
                ai_msg = save_message(session_id=session_id, sender="ai", content=text_out, mode=payload.mode)
                suggested_questions = generate_suggested_questions(clean_msg, text_out, mode=payload.mode)
                yield f"data: {_json.dumps({'type': 'done', 'ai_message': ai_msg, 'sources': None, 'suggested_questions': suggested_questions, 'memory_used': memory_used})}\n\n"
        except Exception as e:
            yield f"data: {_json.dumps({'type': 'error', 'message': 'Stream error occurred'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

