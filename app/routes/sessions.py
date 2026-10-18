import uuid
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from app.models import SessionItem, SessionCreateRequest, ChatMessage
from app.database import (
    create_session,
    get_sessions_by_user,
    get_session_by_id_and_user,
    delete_session_for_user,
    get_messages_by_session
)
from app.security import get_current_user

router = APIRouter(prefix="/api/sessions", tags=["Sessions"])

@router.get("", response_model=List[SessionItem])
def list_sessions(user: dict = Depends(get_current_user)):
    return get_sessions_by_user(user["id"])

@router.post("", response_model=SessionItem)
def create_new_session(payload: SessionCreateRequest, user: dict = Depends(get_current_user)):
    session_id = str(uuid.uuid4())
    new_sess = create_session(
        session_id=session_id,
        user_id=user["id"],
        title=payload.title,
        category=payload.category,
        mode=payload.mode
    )
    return new_sess

@router.get("/{session_id}/messages", response_model=List[ChatMessage])
def get_session_messages(session_id: str, user: dict = Depends(get_current_user)):
    sess = get_session_by_id_and_user(session_id, user["id"])
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found or unauthorized")
    messages = get_messages_by_session(session_id)
    return messages

@router.delete("/{session_id}")
def remove_session(session_id: str, user: dict = Depends(get_current_user)):
    success = delete_session_for_user(session_id, user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Session not found or unauthorized")
    return {"status": "success", "message": "Session deleted"}
