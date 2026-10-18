import uuid
import time
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional

from app.models import (
    ResearchQueryRequest,
    ResearchQueryResponse,
    ResearchSuggestionItem
)
from app.database import (
    save_message,
    get_session_by_id_and_user,
    create_session,
    log_analytics_event
)
from app.services.research_service import (
    gather_web_research,
    synthesize_research_with_first_api,
    generate_suggested_questions,
    get_curated_starter_suggestions
)
from app.security import get_current_user

router = APIRouter(prefix="/api/research", tags=["Web Research Engine"])

@router.post("", response_model=ResearchQueryResponse)
async def handle_web_research_query(
    payload: ResearchQueryRequest,
    user: dict = Depends(get_current_user)
):
    """
    Two-Tier Live Web Research Architecture:
    1. Separate Research API: Researches the overall web and compiles a factual Research Dossier with citations.
    2. First API (Alumni AI Core Engine): Deeply analyzes, evaluates, and synthesizes the researched data.
    3. Suggestion Engine: Generates contextual follow-up question suggestions for user continuation.
    """
    clean_query = payload.query.strip()
    if not clean_query:
        raise HTTPException(status_code=400, detail="Research query cannot be empty")

    start_time = time.time()
    session_id = payload.session_id
    if session_id:
        existing = get_session_by_id_and_user(session_id, user["id"])
        if not existing:
            session_id = None

    if not session_id:
        session_id = str(uuid.uuid4())
        title = "Research: " + clean_query[:30] + ("..." if len(clean_query) > 30 else "")
        create_session(
            session_id=session_id,
            user_id=user["id"],
            title=title,
            category="web_research",
            mode=payload.mode or "professional"
        )

    # Record User Message
    save_message(
        session_id=session_id,
        sender="user",
        content=clean_query,
        mode=payload.mode
    )

    # 1. Separate Research API: Gather overall web findings & citations
    research_data = await gather_web_research(
        query=clean_query,
        depth=payload.depth or "deep",
        max_results=5
    )

    # 2. First API: Analyze and synthesize researched dossier
    analyzed_answer, provider = await synthesize_research_with_first_api(
        query=clean_query,
        research_data=research_data,
        mode=payload.mode or "professional",
        custom_api_key=payload.custom_api_key
    )

    # 3. Suggestion Engine: Generate 3 smart follow-up questions
    suggested_questions = generate_suggested_questions(
        query=clean_query,
        answer=analyzed_answer,
        mode=payload.mode or "professional"
    )

    latency_ms = max(1, int((time.time() - start_time) * 1000))

    # Record AI Response in Database
    save_message(
        session_id=session_id,
        sender="ai",
        content=analyzed_answer,
        mode=payload.mode
    )

    # Log analytics
    try:
        log_analytics_event(
            user_id=user["id"],
            session_id=session_id,
            prompt_chars=len(clean_query),
            response_chars=len(analyzed_answer),
            latency_ms=latency_ms,
            provider_used=f"research_pipeline+{provider}",
            fallback_count=0,
            mode=payload.mode or "professional",
            status="success"
        )
    except Exception as e:
        print(f"[ResearchRoute] Analytics notice: {e}")

    return ResearchQueryResponse(
        session_id=session_id,
        query=clean_query,
        research_summary=research_data.get("research_summary", ""),
        sources=research_data.get("sources", []),
        answer=analyzed_answer,
        suggested_questions=suggested_questions,
        provider=provider
    )

@router.get("/suggestions", response_model=List[ResearchSuggestionItem])
async def get_research_question_suggestions(user: dict = Depends(get_current_user)):
    """
    Returns curated, categorized starter question suggestions for deep web research.
    """
    suggestions = get_curated_starter_suggestions()
    return suggestions
