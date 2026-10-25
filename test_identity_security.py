"""Regression coverage for identity validation, auth safety, and hashing.

Run with a throwaway local database:
    DATABASE_URL=local-sqlite DATABASE_PATH=... python test_identity_security.py
"""

import hashlib
import os
import uuid
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.database import (
    _exec,
    get_connection,
    get_account_removal,
    get_messages_by_session,
    get_sessions_by_user,
    get_user_by_id,
    get_user_by_token,
    hash_password,
    init_db,
    password_needs_rehash,
    save_message,
    save_user,
    create_auth_token,
    create_session,
    verify_password,
)
from app.identity import (
    ACCOUNT_REMOVAL_WARNING,
    derive_display_name,
    detect_suspicious_name,
    username_key,
    validate_display_name,
)

init_db()
client = TestClient(app)


def check(label, condition, detail=""):
    assert condition, f"{label} failed {detail}"
    print(f"[PASS] {label}")


def test_hash_and_legacy_migration():
    stored = hash_password("correct horse battery staple")
    check("PBKDF2 hash format", stored.startswith("pbkdf2_sha256$260000$"))
    check("PBKDF2 verifies", verify_password(stored, "correct horse battery staple"))
    check("PBKDF2 rejects wrong password", not verify_password(stored, "wrong"))
    check("PBKDF2 doesn't need rehash", not password_needs_rehash(stored))

    legacy = hashlib.sha256(b"legacy-pass").hexdigest()
    check("Legacy SHA-256 verifies", verify_password(legacy, "legacy-pass"))
    check("Legacy SHA-256 needs rehash", password_needs_rehash(legacy))
    check("Missing hash never verifies", not verify_password(None, "anything"))

    uid = str(uuid.uuid4())
    email = f"legacy-{uuid.uuid4().hex[:8]}@example.com"
    save_user(uid, "Legacy User", email, "username", False)
    with get_connection() as conn:
        cursor = conn.cursor()
        _exec(cursor, "UPDATE users SET password_hash = %s WHERE id = %s", (legacy, uid))
        conn.commit()

    login = client.post("/api/auth/login", json={
        "username": "Legacy User",
        "password": "legacy-pass",
    })
    check("Legacy account can log in with 4+ chars", login.status_code == 200, login.text)
    migrated = get_user_by_id(uid)
    check("Legacy hash is upgraded on login", migrated["password_hash"].startswith("pbkdf2_sha256$"))
    again = client.post("/api/auth/login", json={
        "username": "Legacy User",
        "password": "legacy-pass",
    })
    check("Migrated account still logs in", again.status_code == 200, again.text)


def test_name_validation():
    valid = [
        "Aarav Sharma", "O'Connor", "Jean-Luc Picard", "A. R. Rahman",
        "Mary Jane Watson", "अंश कुमार", "محمد علي", "van der Waals",
    ]
    for name in valid:
        normalized, code, message = validate_display_name(name)
        check(f"Valid name: {name}", code == "" and normalized, message)

    invalid = [
        "Aarav123", "test_dev", "asdf", "Admin", "Team Alum", "😀", "A",
        "A B", "<script>", "qwertyuiop", "John_Doe", "Hello", "First Last",
        "A..B", "Mary--Jane",
    ]
    for name in invalid:
        normalized, code, message = validate_display_name(name)
        check(f"Rejected non-human name: {name}", normalized is None and code != "", message)

    check("Title-casing", validate_display_name("aarav sharma")[0] == "Aarav Sharma")
    check("Apostrophe normalization", validate_display_name("o’connor")[0] == "O'Connor")
    check("Username key is case-folded", username_key("  AARAV   Sharma ") == "aarav sharma")
    check("Derived name from email", derive_display_name("aarav.sharma99@example.com") == "Aarav Sharma")
    check("Derived fallback is human-readable", derive_display_name("x@example.com") == "New Member")


def test_suspicious_names():
    suspicious = [
        "checking system", "Checking System", "tester", "Tester",
        "mobile device", "MobileDevice", "checkingSystem", "QA Bot",
        "android device", "Android Emulator", "anonymous user",
        "system check", "Windows Device", "test account", "some random person",
    ]
    for name in suspicious:
        reason = detect_suspicious_name(name)
        normalized, code, message = validate_display_name(name)
        check(f"Suspicious name flagged: {name}", bool(reason), reason or "no reason")
        check(
            f"Suspicious name rejected at signup: {name}",
            normalized is None and code in ("suspicious", "reserved", "placeholder"),
            f"code={code} message={message}",
        )

    for name in ["Aarav Sharma", "Nadia Khan", "Jean-Luc Picard", "O'Connor"]:
        check(f"Human name not flagged: {name}", detect_suspicious_name(name) is None)


def test_guest_flow():
    bad = client.post("/api/auth/guest", json={"username": "Aarav123"})
    check("Guest digits rejected", bad.status_code == 400, bad.text)
    bad = client.post("/api/auth/guest", json={"username": "Admin"})
    check("Guest reserved name rejected", bad.status_code == 400, bad.text)
    bad = client.post("/api/auth/guest", json={"username": "checking system"})
    check("Guest system-style name rejected", bad.status_code == 400, bad.text)
    bad = client.post("/api/auth/guest", json={"username": "mobile device"})
    check("Guest device-style name rejected", bad.status_code == 400, bad.text)
    bad = client.post("/api/auth/guest", json={"username": "tester"})
    check("Guest tester name rejected", bad.status_code == 400, bad.text)

    first = client.post("/api/auth/guest", json={"username": "Nadia Khan"})
    check("Guest valid name accepted", first.status_code == 200, first.text)
    first_body = first.json()
    check("Guest name normalized", first_body["username"] == "Nadia Khan")
    check("Guest email is server-generated", first_body["email"].endswith("@guest.alumni.ai"))
    check("Guest is never admin", first_body["is_team_alum"] is False)

    second = client.post("/api/auth/guest", json={"username": "Nadia Khan"})
    check("Duplicate guest accepted with transparent tag", second.status_code == 200, second.text)
    second_body = second.json()
    check("Duplicate guest reports adjustment", second_body["name_adjusted"] is True)
    check("Duplicate guest name is distinct", second_body["username"] != first_body["username"])
    check("Duplicate guest keeps base name", second_body["username"].startswith("Nadia Khan ("))


def test_availability_and_new_accounts():
    available = client.get("/api/auth/username-availability", params={"username": "Ishaan Verma"})
    check("Availability valid", available.status_code == 200 and available.json()["available"] is True)

    invalid = client.get("/api/auth/username-availability", params={"username": "Ishaan123"})
    check("Availability rejects digits", invalid.json()["valid"] is False)

    created = client.post("/api/auth/login", json={
        "username": "ishaan verma",
        "password": "StrongPass123",
    })
    check("Name-only account created", created.status_code == 200, created.text)
    created_body = created.json()
    check("New name is normalized", created_body["username"] == "Ishaan Verma")
    check("New name-only account gets synthetic email", created_body["email"].endswith("@users.alumni.ai"))
    check("New account is not admin", created_body["is_team_alum"] is False)

    taken = client.post("/api/auth/login", json={
        "username": "Ishaan Verma",
        "password": "StrongPass123",
    })
    check("Taken name does not silently log into another account", taken.status_code == 200)
    # It is the same account, so existing login is expected; a fresh email with
    # the same display name must be the one that is rejected.
    collision = client.post("/api/auth/login", json={
        "username": "Ishaan Verma",
        "email": f"ishaan-{uuid.uuid4().hex[:8]}@example.com",
        "password": "StrongPass123",
    })
    check("Name taken by a different email is a 409", collision.status_code == 409, collision.text)

    short = client.post("/api/auth/login", json={
        "username": "Short Pass",
        "password": "1234567",
    })
    check("New accounts need 8+ character passwords", short.status_code == 400, short.text)

    bad_name = client.post("/api/auth/login", json={
        "username": "NewUser123",
        "password": "StrongPass123",
    })
    check("New account digit name rejected", bad_name.status_code == 400, bad_name.text)

    email = f"noor-{uuid.uuid4().hex[:8]}@example.com"
    with_email = client.post("/api/auth/login", json={
        "username": "Noor Ahmed",
        "email": email,
        "password": "StrongPass123",
        "is_team_alum": True,
    })
    check("Email account created", with_email.status_code == 200, with_email.text)
    check("Client cannot self-grant admin", with_email.json()["is_team_alum"] is False)

    existing_email_login = client.post("/api/auth/login", json={
        "username": "Other Person",
        "email": email,
        "password": "StrongPass123",
    })
    check("Existing email + correct password signs in", existing_email_login.status_code == 200, existing_email_login.text)
    check("Existing email login keeps the original account", existing_email_login.json()["id"] == with_email.json()["id"])
    wrong_password = client.post("/api/auth/login", json={
        "email": email,
        "password": "WrongPass123",
    })
    check("Existing email + wrong password is 401", wrong_password.status_code == 401, wrong_password.text)

    admin_new = client.post("/api/auth/login", json={
        "username": "Admin Person",
        "email": "new-admin@team.alum",
        "password": "StrongPass123",
    })
    check("New @team.alum password account blocked", admin_new.status_code == 403, admin_new.text)

    check("Availability after create", client.get(
        "/api/auth/username-availability", params={"username": "Ishaan Verma"}
    ).json()["available"] is False)


def test_ambiguous_and_google_accounts():
    password = "StrongPass123"
    duplicate_name = "Duplicate Name"
    first_id = str(uuid.uuid4())
    second_id = str(uuid.uuid4())
    save_user(first_id, duplicate_name, f"dup1-{uuid.uuid4().hex[:6]}@example.com", "username", False, password)
    save_user(second_id, duplicate_name, f"dup2-{uuid.uuid4().hex[:6]}@example.com", "username", False, password)

    ambiguous = client.post("/api/auth/login", json={"username": duplicate_name, "password": password})
    check("Duplicate username fails safely with 409", ambiguous.status_code == 409, ambiguous.text)

    first_email = get_user_by_id(first_id)["email"]
    by_email = client.post("/api/auth/login", json={"email": first_email, "password": password})
    check("Duplicate-username account can still log in by email", by_email.status_code == 200, by_email.text)
    check("Email login returns the correct row", by_email.json()["id"] == first_id)

    duplicate_email = f"same-{uuid.uuid4().hex[:6]}@example.com"
    save_user(str(uuid.uuid4()), "Same One", duplicate_email, "username", False, password)
    save_user(str(uuid.uuid4()), "Same Two", duplicate_email, "username", False, password)
    ambiguous_email = client.post("/api/auth/login", json={"email": duplicate_email, "password": password})
    check("Duplicate email fails safely with 409", ambiguous_email.status_code == 409, ambiguous_email.text)

    google_email = f"google-{uuid.uuid4().hex[:6]}@example.com"
    google_id = str(uuid.uuid4())
    save_user(google_id, "Google User", google_email, "google", False, password)
    google_login = client.post("/api/auth/login", json={"email": google_email, "password": password})
    check("Google account rejects password login", google_login.status_code == 400, google_login.text)

    passwordless_id = str(uuid.uuid4())
    passwordless_email = f"nopw-{uuid.uuid4().hex[:6]}@example.com"
    save_user(passwordless_id, "No Password", passwordless_email, "username", False)
    no_password = client.post("/api/auth/login", json={"email": passwordless_email, "password": password})
    check("Passwordless account rejects password login", no_password.status_code == 400, no_password.text)

    admin_email = f"admin-{uuid.uuid4().hex[:6]}@team.alum"
    admin_id = str(uuid.uuid4())
    save_user(admin_id, "Admin Tester", admin_email, "alum", True, password)
    admin_login = client.post("/api/auth/login", json={"email": admin_email, "password": password})
    check("Existing allowlisted account can log in", admin_login.status_code == 200, admin_login.text)
    check("Allowlisted account receives admin flag", admin_login.json()["is_team_alum"] is True)


def test_token_expiry():
    uid = str(uuid.uuid4())
    email = f"token-{uuid.uuid4().hex[:6]}@example.com"
    save_user(uid, "Token Tester", email, "username", False, "StrongPass123")
    login = client.post("/api/auth/login", json={"email": email, "password": "StrongPass123"})
    token = login.json()["token"]
    check("Fresh token works", get_user_by_token(token) is not None)

    old = (datetime.utcnow() - timedelta(days=91)).isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        _exec(cursor, "UPDATE auth_tokens SET created_at = %s WHERE token = %s", (old, token))
        conn.commit()
    check("Expired token is rejected", get_user_by_token(token) is None)


def test_admin_removal_flow():
    founder_email = f"reviewer-{uuid.uuid4().hex[:6]}@team.alum"
    founder_id = str(uuid.uuid4())
    save_user(founder_id, "Founder Reviewer", founder_email, "alum", True, "StrongPass123")
    founder_login = client.post("/api/auth/login", json={
        "email": founder_email,
        "password": "StrongPass123",
    })
    check("Founder can sign in for review", founder_login.status_code == 200, founder_login.text)
    founder_headers = {"Authorization": f"Bearer {founder_login.json()['token']}"}

    target_id = str(uuid.uuid4())
    target_email = f"checking-{uuid.uuid4().hex[:6]}@example.com"
    save_user(target_id, "Checking System", target_email, "username", False, "StrongPass123")
    target_headers = {"Authorization": f"Bearer {create_auth_token(target_id)}"}

    normal_id = str(uuid.uuid4())
    save_user(
        normal_id, "Aarav Sharma", f"real-{uuid.uuid4().hex[:6]}@example.com",
        "username", False, "StrongPass123",
    )

    forbidden = client.post(
        f"/api/analytics/users/{target_id}/remove",
        headers=target_headers,
        json={"confirm_username": "Checking System"},
    )
    check("Non-admin cannot remove accounts", forbidden.status_code == 403, forbidden.text)

    not_suspicious = client.post(
        f"/api/analytics/users/{normal_id}/remove",
        headers=founder_headers,
        json={"confirm_username": "Aarav Sharma"},
    )
    check("Non-suspicious account is not removable", not_suspicious.status_code == 400, not_suspicious.text)

    wrong_confirm = client.post(
        f"/api/analytics/users/{target_id}/remove",
        headers=founder_headers,
        json={"confirm_username": "wrong name"},
    )
    check("Removal requires exact username confirmation", wrong_confirm.status_code == 400, wrong_confirm.text)

    # History is created before removal and must survive the review action.
    session_id = str(uuid.uuid4())
    create_session(session_id, target_id, "Preserved workspace")
    save_message(session_id, "user", "Please keep this history")

    removed = client.post(
        f"/api/analytics/users/{target_id}/remove",
        headers=founder_headers,
        json={"confirm_username": "Checking System"},
    )
    check("Founder removes suspicious account", removed.status_code == 200, removed.text)
    check("Removal reports data preservation", removed.json().get("data_preserved") is True)
    check("Removal warning matches requested wording", removed.json().get("warning") == ACCOUNT_REMOVAL_WARNING)
    check("User row still exists", get_user_by_id(target_id) is not None)
    check("Removal record exists", bool(get_account_removal(target_id)))
    check("Session history still exists", len(get_sessions_by_user(target_id)) == 1)
    check("Message history still exists", len(get_messages_by_session(session_id)) == 1)

    me = client.get("/api/auth/me", headers=target_headers)
    check("Removed user can read the warning", me.status_code == 200, me.text)
    check("Removed status is reported", me.json().get("account_removed") is True)
    check("Warning text is delivered", me.json().get("removal_warning") == ACCOUNT_REMOVAL_WARNING)

    blocked = client.get("/api/sessions", headers=target_headers)
    check("Removed user loses workspace access", blocked.status_code == 403, blocked.text)
    check("Blocked response carries the warning", ACCOUNT_REMOVAL_WARNING in blocked.text)

    chat_blocked = client.post(
        "/api/chat",
        headers=target_headers,
        json={"message": "Are you still there?", "mode": "basic"},
    )
    check("Removed user loses chat access", chat_blocked.status_code == 403, chat_blocked.text)
    check("Chat warning is delivered", ACCOUNT_REMOVAL_WARNING in chat_blocked.text)

    relogin = client.post("/api/auth/login", json={
        "email": target_email,
        "password": "StrongPass123",
    })
    check("Removed account cannot sign in again", relogin.status_code == 403, relogin.text)

    users_res = client.get("/api/analytics/users", headers=founder_headers)
    check("Admin users list is available", users_res.status_code == 200, users_res.text)
    target_row = next(u for u in users_res.json()["users"] if u["id"] == target_id)
    check("Admin list flags suspicious name", target_row.get("suspicious") is True)
    check("Admin list shows removed state", target_row.get("account_removed") is True)
    check("Admin list keeps removal warning", target_row.get("removal_warning") == ACCOUNT_REMOVAL_WARNING)

    again = client.post(
        f"/api/analytics/users/{target_id}/remove",
        headers=founder_headers,
        json={"confirm_username": "Checking System"},
    )
    check("Repeated removal is idempotent", again.status_code == 200 and again.json().get("status") == "already_removed")

    self_remove = client.post(
        f"/api/analytics/users/{founder_id}/remove",
        headers=founder_headers,
        json={"confirm_username": "Founder Reviewer"},
    )
    check("Founder cannot remove own admin account", self_remove.status_code in (400, 403), self_remove.text)


if __name__ == "__main__":
    if os.getenv("DATABASE_URL", "").startswith(("postgres://", "postgresql://")):
        raise SystemExit("Refusing to run identity tests against a remote database.")
    test_hash_and_legacy_migration()
    test_name_validation()
    test_suspicious_names()
    test_guest_flow()
    test_availability_and_new_accounts()
    test_ambiguous_and_google_accounts()
    test_token_expiry()
    test_admin_removal_flow()
    print("=" * 60)
    print("ALL IDENTITY & SECURITY REGRESSION TESTS PASSED")
    print("=" * 60)
