from typing import List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from app.security import get_current_user
from app.database import (
    get_user_memories,
    add_user_memory,
    delete_user_memory,
    clear_user_memories,
)

router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemoryAddRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=500, description="A fact to remember about the user")
    source: str = Field(default="manual", max_length=32)


class MemoryItem(BaseModel):
    id: int
    content: str
    source: str
    created_at: str


@router.get("")
def list_memories(user: dict = Depends(get_current_user)):
    rows = get_user_memories(user["id"])
    return {"memories": rows, "count": len(rows)}


@router.post("")
def create_memory(payload: MemoryAddRequest, user: dict = Depends(get_current_user)):
    row = add_user_memory(user["id"], payload.content, payload.source or "manual")
    if not row:
        raise HTTPException(status_code=409, detail="Memory already exists or memory limit reached")
    return {"memory": row}


@router.delete("/{memory_id}")
def remove_memory(memory_id: int, user: dict = Depends(get_current_user)):
    if not delete_user_memory(user["id"], memory_id):
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"deleted": memory_id}


@router.delete("")
def clear_all(user: dict = Depends(get_current_user)):
    clear_user_memories(user["id"])
    return {"cleared": True}
