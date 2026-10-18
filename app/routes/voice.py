import time
from fastapi import APIRouter, Depends
from app.models import VoiceQueryRequest, VoiceQueryResponse
from app.services.voice_service import process_voice_query
from app.security import get_current_user
from app.database import log_analytics_event

router = APIRouter(prefix="/api/voice", tags=["Voice Assistant May"])

@router.post("/query", response_model=VoiceQueryResponse)
async def handle_voice_query(payload: VoiceQueryRequest, user: dict = Depends(get_current_user)):
    start_time = time.time()
    clean_query = payload.query.strip()
    result = await process_voice_query(
        query=clean_query,
        mode=payload.mode,
        session_id=payload.session_id,
        user=user,
        custom_api_key=payload.custom_api_key,
        speaker=payload.speaker,
        language=payload.language
    )
    latency_ms = max(1, int((time.time() - start_time) * 1000))
    try:
        log_analytics_event(
            user_id=user["id"],
            session_id=payload.session_id or "voice_interaction",
            prompt_chars=len(clean_query),
            response_chars=len(result.get("reply", "")),
            latency_ms=latency_ms,
            provider_used="voice_may",
            fallback_count=0,
            mode=payload.mode,
            status="success"
        )
    except Exception as e:
        print(f"[Analytics Voice] Log notice: {e}")
    return result

