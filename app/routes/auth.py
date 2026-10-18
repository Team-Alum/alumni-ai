import uuid
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional
from pydantic import BaseModel
from app.models import LoginRequest, UserResponse
from app.database import (
    save_user,
    get_user_by_email,
    get_user_by_email_or_username,
    create_auth_token,
    delete_auth_token,
    verify_password
)
from app.security import get_current_user
from app.config import GOOGLE_CLIENT_ID, is_admin_email

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class GoogleCredentialRequest(BaseModel):
    credential: str


def _is_founder_email(email: str) -> bool:
    # Delegates to the central allowlist (ADMIN_EMAILS + @team.alum domain).
    return is_admin_email(email)


@router.get("/config")
def get_auth_config():
    return {
        "google_client_id": GOOGLE_CLIENT_ID
    }


@router.post("/google", response_model=UserResponse)
def google_oauth_login(payload: GoogleCredentialRequest):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="Google Sign-In is not configured on this server."
        )
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
        info = google_id_token.verify_oauth2_token(
            payload.credential, google_requests.Request(), GOOGLE_CLIENT_ID
        )
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Google sign-in verification failed. Please try again."
        )

    if not info.get("email") or not info.get("email_verified", False):
        raise HTTPException(
            status_code=401,
            detail="Your Google account email is not verified."
        )

    email = info["email"].strip().lower()
    display_name = (info.get("name") or "").strip() or email.split("@")[0]

    existing = get_user_by_email(email)
    if existing:
        user_id = existing["id"]
        user = save_user(
            user_id=user_id,
            username=existing.get("username") or display_name,
            email=email,
            login_method="google",
            is_team_alum=_is_founder_email(email),
            password=None
        )
    else:
        user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, email))
        user = save_user(
            user_id=user_id,
            username=display_name,
            email=email,
            login_method="google",
            is_team_alum=_is_founder_email(email),
            password=None
        )

    token = create_auth_token(user_id)
    return {**user, "token": token}


@router.post("/guest", response_model=UserResponse)
def guest_login():
    guest_suffix = uuid.uuid4().hex[:5].upper()
    username = f"Guest {guest_suffix}"
    email = f"guest_{guest_suffix.lower()}@guest.alumni.ai"
    user_id = str(uuid.uuid4())
    user = save_user(
        user_id=user_id,
        username=username,
        email=email,
        login_method="guest",
        is_team_alum=False,
        password=None
    )
    token = create_auth_token(user_id)
    return {
        **user,
        "token": token
    }


@router.post("/login", response_model=UserResponse)
def login_user(payload: LoginRequest):
    email_clean = (payload.email or "").strip().lower()
    username_clean = (payload.username or "").strip()
    password_clean = (payload.password or "").strip()

    # Fast-path for guest login via /api/auth/login
    if payload.login_method == "guest":
        guest_suffix = uuid.uuid4().hex[:5].upper()
        username_clean = username_clean or f"Guest {guest_suffix}"
        email_clean = email_clean or f"guest_{guest_suffix.lower()}@guest.alumni.ai"
        user_id = str(uuid.uuid4())
        user = save_user(
            user_id=user_id,
            username=username_clean,
            email=email_clean,
            login_method="guest",
            is_team_alum=False,
            password=None
        )
        token = create_auth_token(user_id)
        return {
            **user,
            "token": token
        }

    # Google logins must go through the verified /api/auth/google endpoint.
    # Plain /login accepts no Google credentials, so no identity can be spoofed here.
    if payload.login_method == "google":
        raise HTTPException(
            status_code=400,
            detail="Please use the Google Sign-In button to log in with Google."
        )

    # 1. Mandatory password validation for direct / non-OAuth logins
    if payload.login_method not in ("guest",):
        if not password_clean:
            raise HTTPException(
                status_code=400,
                detail="Password is required. Please provide a valid password."
            )
        if len(password_clean) < 4:
            raise HTTPException(
                status_code=400,
                detail="Password must be at least 4 characters long."
            )
    
    # 2. Check if user already exists by email or username
    existing_user = None
    if email_clean:
        existing_user = get_user_by_email_or_username(email_clean)
    if not existing_user and username_clean:
        existing_user = get_user_by_email_or_username(username_clean)
    
    if existing_user:
        stored_hash = existing_user.get("password_hash")
        existing_method = existing_user.get("login_method", payload.login_method)

        if payload.login_method != "google":
            # Guest rows are not password accounts — refuse password login on them.
            if existing_method == "guest":
                raise HTTPException(
                    status_code=400,
                    detail="This is a temporary guest session. Please continue as a guest."
                )
            # Passwordless (Google-created) accounts must use the Google flow.
            # Without this check, knowing only a username would grant full
            # account access because there is no hash to verify against.
            if not stored_hash:
                raise HTTPException(
                    status_code=400,
                    detail="This account was created with Google Sign-In. Please sign in with Google instead."
                )
            if not verify_password(stored_hash, password_clean):
                raise HTTPException(
                    status_code=401,
                    detail="Incorrect password for this account. Please try again."
                )

        # Never swap emails: a username match with a *different* supplied
        # email is treated as non-matching credentials (prevents rewriting a
        # victim row's email to an admin address).
        if (
            email_clean
            and existing_user.get("email")
            and email_clean != (existing_user.get("email") or "").strip().lower()
        ):
            raise HTTPException(
                status_code=401,
                detail="Incorrect email/username or password for this account."
            )

        user_id = existing_user["id"]
        username_final = username_clean if username_clean else existing_user["username"]
        email_final = email_clean if email_clean else existing_user["email"]
        # Admin flag is derived ONLY from the verified email allowlist —
        # legacy/attacker-set DB flags are discarded on every login.
        is_team_alum_final = is_admin_email(email_final)
        user = save_user(
            user_id=user_id,
            username=username_final,
            email=email_final,
            login_method=existing_method,
            is_team_alum=is_team_alum_final,
            password=password_clean if password_clean else None
        )
    else:
        # Determine email and friendly username for new accounts
        if not email_clean:
            email_clean = f"{username_clean.lower().replace(' ', '')}@alumni.ai"
        if not username_clean:
            raw_prefix = email_clean.split("@")[0]
            username_clean = raw_prefix.replace(".", " ").replace("_", " ").title() if raw_prefix else "Scholar"

        # SECURITY: an allowlisted admin address can never be claimed through
        # unverified password registration (email ownership is only proven by
        # Google Sign-In). This prevents anyone from pre-registering
        # teamalumorg@gmail.com with a password of their choice.
        if is_admin_email(email_clean):
            raise HTTPException(
                status_code=403,
                detail="This email address must be registered via Google Sign-In."
            )

        user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, email_clean.lower()))
        # SECURITY: client-supplied payload.is_team_alum is IGNORED.
        # New password accounts are never admin; admin status is granted only
        # when an allowlisted email is proven through Google OAuth.
        user = save_user(
            user_id=user_id,
            username=username_clean,
            email=email_clean,
            login_method=payload.login_method,
            is_team_alum=False,
            password=password_clean if password_clean else None
        )
    
    # Generate secure session token
    token = create_auth_token(user_id)
    return {
        **user,
        "token": token
    }


@router.get("/me")
def get_me(user: dict = Depends(get_current_user)):
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "login_method": user["login_method"],
        "is_team_alum": bool(user["is_team_alum"])
    }

@router.post("/logout")
def logout_user(authorization: Optional[str] = Header(None)):
    if authorization:
        parts = authorization.split(" ")
        token = parts[1] if len(parts) == 2 and parts[0].lower() == "bearer" else authorization
        delete_auth_token(token)
    return {"status": "success", "message": "Logged out"}
