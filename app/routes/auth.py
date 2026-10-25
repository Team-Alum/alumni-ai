import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel

from app.models import LoginRequest, UserResponse
from app.database import (
    save_user,
    get_users_by_email,
    get_users_by_username,
    username_exists,
    create_auth_token,
    delete_auth_token,
    verify_password,
    password_needs_rehash,
)
from app.identity import (
    GUEST_NAME_MAX,
    NAME_MAX,
    derive_display_name,
    is_valid_email,
    synthetic_email_for_name,
    validate_display_name,
)
from app.security import get_current_user
from app.config import GOOGLE_CLIENT_ID, is_admin_email

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class GoogleCredentialRequest(BaseModel):
    credential: str


class GuestLoginRequest(BaseModel):
    username: Optional[str] = None


def _unique_account_name(name: str, max_length: int = NAME_MAX) -> tuple[str, bool]:
    """Keep account display names distinct without ever rewriting a login row."""
    if not username_exists(name):
        return name, False
    suffix = f" ({uuid.uuid4().hex[:4].upper()})"
    candidate = f"{name[:max_length - len(suffix)].strip()}{suffix}"
    if not username_exists(candidate):
        return candidate, True
    # Extremely unlikely, but never loop forever on a collision.
    return f"{name[:max_length - 10].strip()} ({uuid.uuid4().hex[:6].upper()})", True


def _create_guest_account(raw_name: Optional[str]) -> dict:
    """Single hardened path used by both /guest and the /login guest fast-path.

    The email is always server-generated so a guest can never claim (or shadow)
    a real account's address. Duplicate friendly names get a transparent tag.
    """
    display_name, error_code, message = validate_display_name(
        raw_name, max_length=GUEST_NAME_MAX
    )
    if error_code:
        raise HTTPException(status_code=400, detail=message)

    final_name, adjusted = _unique_account_name(display_name, GUEST_NAME_MAX)
    guest_id = uuid.uuid4().hex
    user = save_user(
        user_id=str(uuid.uuid4()),
        username=final_name,
        email=f"guest_{guest_id[:10]}@guest.alumni.ai",
        login_method="guest",
        is_team_alum=False,
        password=None,
    )
    return {
        **user,
        "token": create_auth_token(user["id"]),
        "name_adjusted": adjusted,
    }


def _is_founder_email(email: str) -> bool:
    # Delegates to the central allowlist (ADMIN_EMAILS + @team.alum domain).
    return is_admin_email(email)


@router.get("/config")
def get_auth_config():
    return {"google_client_id": GOOGLE_CLIENT_ID}


@router.get("/username-availability")
def username_availability(username: str = ""):
    """Public, validation-first availability check used by the login card.

    It deliberately returns friendly guidance instead of a bare boolean so the
    UI can explain *why* a name cannot be used.
    """
    normalized, error_code, message = validate_display_name(
        username, max_length=NAME_MAX
    )
    if error_code:
        return {
            "available": False,
            "valid": False,
            "username": "",
            "message": message,
        }
    if username_exists(normalized):
        return {
            "available": False,
            "valid": True,
            "username": normalized,
            "message": "That username is already taken. Please choose another one.",
        }
    return {
        "available": True,
        "valid": True,
        "username": normalized,
        "message": "That name is available.",
    }


@router.post("/google", response_model=UserResponse)
def google_oauth_login(payload: GoogleCredentialRequest):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="Google Sign-In is not configured on this server.",
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
            detail="Google sign-in verification failed. Please try again.",
        )

    if not info.get("email") or not info.get("email_verified", False):
        raise HTTPException(
            status_code=401,
            detail="Your Google account email is not verified.",
        )

    email = info["email"].strip().lower()
    matches = get_users_by_email(email)
    if len(matches) > 1:
        raise HTTPException(
            status_code=409,
            detail="This email is linked to more than one account. Please contact Team Alum support.",
        )
    existing = matches[0] if matches else None

    raw_name = (info.get("name") or "").strip() or email.split("@")[0]
    normalized, error_code, _ = validate_display_name(raw_name)
    display_name = normalized if not error_code else derive_display_name(email)
    adjusted = False

    if existing:
        user_id = existing["id"]
        # Google proves mailbox ownership. Clear any legacy password so a
        # password login can never be used against a Google account.
        user = save_user(
            user_id=user_id,
            username=existing.get("username") or display_name,
            email=email,
            login_method="google",
            is_team_alum=_is_founder_email(email),
            password=None,
            clear_password=True,
        )
    else:
        display_name, adjusted = _unique_account_name(display_name, NAME_MAX)
        user_id = str(uuid.uuid4())
        user = save_user(
            user_id=user_id,
            username=display_name,
            email=email,
            login_method="google",
            is_team_alum=_is_founder_email(email),
            password=None,
        )

    token = create_auth_token(user_id)
    return {**user, "token": token, "name_adjusted": adjusted}


@router.post("/guest", response_model=UserResponse)
def guest_login(payload: Optional[GuestLoginRequest] = None):
    """Guest access asks for a display name so the workspace can greet the user."""
    return _create_guest_account(payload.username if payload else None)


@router.post("/login", response_model=UserResponse)
def login_user(payload: LoginRequest):
    email_raw = (payload.email or "").strip()
    username_raw = (payload.username or "").strip()
    password_clean = (payload.password or "").strip()

    # Fast-path for guest login via /api/auth/login.
    if payload.login_method == "guest":
        return _create_guest_account(payload.username)

    # Google logins must go through the verified /api/auth/google endpoint.
    if payload.login_method == "google":
        raise HTTPException(
            status_code=400,
            detail="Please use the Google Sign-In button to log in with Google.",
        )

    if not password_clean:
        raise HTTPException(
            status_code=400,
            detail="Password is required. Please provide a valid password.",
        )
    if len(password_clean) < 4:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 4 characters long.",
        )

    email_clean = email_raw.lower()
    username_clean = username_raw

    # Be forgiving if an API client puts the email in the username field.
    if email_clean and "@" not in email_clean:
        if not username_clean:
            username_clean = email_clean
        email_clean = ""
    if username_clean and "@" in username_clean:
        if not email_clean:
            email_clean = username_clean.lower()
        username_clean = ""

    # ---------------------------------------------------------
    # Resolve the account. Email wins when supplied; duplicate
    # usernames/emails fail safely instead of returning a random row.
    # ---------------------------------------------------------
    email_matches = get_users_by_email(email_clean) if email_clean else []
    if len(email_matches) > 1:
        raise HTTPException(
            status_code=409,
            detail="This email is linked to more than one account. Please contact Team Alum support.",
        )
    email_user = email_matches[0] if email_matches else None

    username_matches = []
    if not email_user and username_clean:
        username_matches = get_users_by_username(username_clean)
        if len(username_matches) > 1:
            raise HTTPException(
                status_code=409,
                detail="This username is linked to more than one account. Please sign in with your email address.",
            )
        if username_matches and email_clean:
            # A supplied email that does not own this username must never be
            # allowed to take it over or silently rewrite the row.
            raise HTTPException(
                status_code=409,
                detail="That username is already taken. Please sign in with its email address or choose another name.",
            )

    existing_user = email_user or (username_matches[0] if username_matches else None)

    if existing_user:
        existing_email = (existing_user.get("email") or "").strip().lower()
        if email_clean and email_clean != existing_email:
            raise HTTPException(
                status_code=401,
                detail="Incorrect email/username or password for this account.",
            )

        stored_hash = existing_user.get("password_hash")
        existing_method = existing_user.get("login_method") or payload.login_method

        if existing_method == "guest":
            raise HTTPException(
                status_code=400,
                detail="This is a temporary guest session. Please continue as a guest.",
            )
        if existing_method == "google":
            raise HTTPException(
                status_code=400,
                detail="This account was created with Google Sign-In. Please sign in with Google instead.",
            )
        if not stored_hash:
            raise HTTPException(
                status_code=400,
                detail="This account has no password set. Please sign in with Google or contact Team Alum support.",
            )
        if not verify_password(stored_hash, password_clean):
            raise HTTPException(
                status_code=401,
                detail="Incorrect password for this account. Please try again.",
            )

        user_id = existing_user["id"]
        username_final = existing_user["username"]
        email_final = existing_user["email"]
        login_method_final = "alum" if _is_founder_email(email_final) else existing_method
        # Transparently upgrade legacy SHA-256 hashes on the next login.
        user = save_user(
            user_id=user_id,
            username=username_final,
            email=email_final,
            login_method=login_method_final,
            is_team_alum=_is_founder_email(email_final),
            password=password_clean if password_needs_rehash(stored_hash) else None,
        )
        return {
            **user,
            "token": create_auth_token(user_id),
            "name_adjusted": False,
        }

    # ---------------------------------------------------------
    # New account. Usernames must look like a human name, be unique,
    # and new password accounts need at least 8 characters.
    # ---------------------------------------------------------
    if not email_clean and not username_clean:
        raise HTTPException(
            status_code=400,
            detail="Please enter your email address or the name you'd like us to use.",
        )

    if email_clean:
        if not is_valid_email(email_clean):
            raise HTTPException(
                status_code=400,
                detail="Please enter a valid email address.",
            )
        if _is_founder_email(email_clean):
            raise HTTPException(
                status_code=403,
                detail="This email address must be registered via Google Sign-In.",
            )
        email_final = email_clean
        if username_clean:
            display_name, error_code, message = validate_display_name(
                username_clean, max_length=NAME_MAX
            )
            if error_code:
                raise HTTPException(status_code=400, detail=message)
            name_was_derived = False
        else:
            display_name = derive_display_name(email_final)
            name_was_derived = True
    else:
        display_name, error_code, message = validate_display_name(
            username_clean, max_length=NAME_MAX
        )
        if error_code:
            raise HTTPException(status_code=400, detail=message)
        email_final = synthetic_email_for_name(display_name)
        name_was_derived = False

    if len(password_clean) < 8:
        raise HTTPException(
            status_code=400,
            detail="For a new account, please use at least 8 characters for your password.",
        )

    if get_users_by_email(email_final):
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists. Please sign in instead.",
        )

    adjusted = False
    if username_exists(display_name):
        if name_was_derived:
            display_name, adjusted = _unique_account_name(display_name, NAME_MAX)
        else:
            raise HTTPException(
                status_code=409,
                detail="That username is already taken. Please choose another one.",
            )

    user = save_user(
        user_id=str(uuid.uuid4()),
        username=display_name,
        email=email_final,
        login_method="email" if email_clean else "username",
        is_team_alum=False,
        password=password_clean,
    )
    return {
        **user,
        "token": create_auth_token(user["id"]),
        "name_adjusted": adjusted,
    }


@router.get("/me")
def get_me(user: dict = Depends(get_current_user)):
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "login_method": user["login_method"],
        "is_team_alum": bool(user["is_team_alum"]),
    }


@router.post("/logout")
def logout_user(authorization: Optional[str] = Header(None)):
    if authorization:
        parts = authorization.split(" ")
        token = parts[1] if len(parts) == 2 and parts[0].lower() == "bearer" else authorization
        delete_auth_token(token)
    return {"status": "success", "message": "Logged out"}
