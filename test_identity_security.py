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
    get_user_by_id,
    get_user_by_token,
    hash_password,
    init_db,
    password_needs_rehash,
    save_user,
    verify_password,
)
from app.identity import derive_display_name, username_key, validate_display_name

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


def test_guest_flow():
    bad = client.post("/api/auth/guest", json={"username": "Aarav123"})
    check("Guest digits rejected", bad.status_code == 400, bad.text)
    bad = client.post("/api/auth/guest", json={"username": "Admin"})
    check("Guest reserved name rejected", bad.status_code == 400, bad.text)

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


if __name__ == "__main__":
    if os.getenv("DATABASE_URL", "").startswith(("postgres://", "postgresql://")):
        raise SystemExit("Refusing to run identity tests against a remote database.")
    test_hash_and_legacy_migration()
    test_name_validation()
    test_guest_flow()
    test_availability_and_new_accounts()
    test_ambiguous_and_google_accounts()
    test_token_expiry()
    print("=" * 60)
    print("ALL IDENTITY & SECURITY REGRESSION TESTS PASSED")
    print("=" * 60)
