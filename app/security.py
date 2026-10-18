import time
from collections import defaultdict
from typing import Dict, List, Optional
from fastapi import Header, HTTPException, Depends
from app.database import get_user_by_token
from app.config import is_admin_email

# In-memory sliding window rate limiter: user_id -> list of timestamps
_RATE_LIMIT_BUCKET: Dict[str, List[float]] = defaultdict(list)
RATE_LIMIT_WINDOW = 60 # 60 seconds
MAX_REQUESTS_NORMAL = 20
MAX_REQUESTS_TEAM_ALUM = 60

def get_current_user(authorization: Optional[str] = Header(None)) -> Dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication token required. Please sign in.")
    
    parts = authorization.split(" ")
    token = parts[1] if len(parts) == 2 and parts[0].lower() == "bearer" else authorization
    
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session. Please sign in again.")

    # Admin normalization: the email allowlist is the SINGLE source of truth.
    # Client-supplied or legacy DB is_team_alum flags are discarded here —
    # a user only carries admin rights if their verified email is allowlisted.
    user["is_team_alum"] = 1 if is_admin_email(user.get("email")) else 0

    # Check rate limit
    now = time.time()
    user_id = user["id"]
    is_team_alum = bool(user.get("is_team_alum", 0))
    limit = MAX_REQUESTS_TEAM_ALUM if is_team_alum else MAX_REQUESTS_NORMAL
    
    # Evict timestamps older than 60s
    _RATE_LIMIT_BUCKET[user_id] = [t for t in _RATE_LIMIT_BUCKET[user_id] if now - t < RATE_LIMIT_WINDOW]
    
    if len(_RATE_LIMIT_BUCKET[user_id]) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({limit} requests/min). Please wait a few seconds before trying again."
        )
        
    _RATE_LIMIT_BUCKET[user_id].append(now)
    return user
