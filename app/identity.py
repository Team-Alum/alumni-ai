"""Human-name and account-identity helpers.

The goal is not to guess someone's real legal name -- that is impossible and
exclusionary. Instead we reject the things that are clearly *not* a human name:
digits, markup, emoji, handles, placeholder words, and keyboard mash. We keep
Unicode letters and combining marks so names in Hindi, Arabic, Tamil, etc. work.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional, Tuple

NAME_MIN = 2
NAME_MAX = 40
GUEST_NAME_MAX = 32
NAME_MAX_WORDS = 5
NAME_MAX_WORD_LEN = 24

# Apostrophes/hyphens are normal in names; periods are allowed for initials.
_APOSTROPHES = {"'", "’", "ʼ"}
_HYPHENS = {"-", "‐", "‑", "‒", "–", "—"}
_PERIODS = {".", "．"}

_RESERVED_COMPACT = {
    "sudarshan", "sudarshanhadmode", "soham", "teamalum", "teamalumorg",
    "alumni", "alumniai", "admin", "administrator", "root", "founder",
    "foundersudarshan", "cofounder", "moderator", "support", "system", "may",
    "pengu", "official", "staff", "owner", "security", "billing", "helpdesk",
    "team", "alum",
}
_RESERVED_PREFIXES = (
    "teamalum", "alumni", "admin", "guest", "support", "moderator",
    "system", "official",
)
_PLACEHOLDER_COMPACT = {
    "test", "testuser", "testing", "guest", "guestuser", "user", "username",
    "name", "fullname", "yourname", "myname", "anonymous", "unknown", "null",
    "none", "na", "asdf", "asdfasdf", "qwerty", "qwertyuiop", "zxcv",
    "zxcvbn", "abc", "abcd", "xyz", "demo", "sample", "example", "temp",
    "temporary", "newuser", "justme", "human", "realname", "firstname",
    "lastname", "nickname", "scholar", "student", "professor", "teacher",
    "hello", "hi", "hey", "there", "buddy", "friend", "bro", "dude", "noname",
    "namehere", "yournamehere", "firstlast", "lorem", "ipsum", "qazwsx",
}
_KEYBOARD_FRAGMENTS = (
    "qwerty", "asdf", "zxcv", "hjkl", "uiop", "poiu", "lkjh", "mnbv",
    "qazwsx", "wsxedc", "edcrfv", "rfvtgb", "tgbyhn", "yhnujm", "abcdef",
)

# Names that describe a device, a test run, or an anonymous session rather
# than a person. These are also used to flag legacy rows in the admin panel,
# so the list deliberately covers the common "checking system", "tester",
# "mobile device" style names seen in production.
_SUSPICIOUS_TOKENS = {
    "admin", "administrator", "android", "anonymous", "api", "automated",
    "automation", "bot", "browser", "checker", "checking", "computer",
    "crawler", "debug", "desktop", "device", "dummy", "emulator", "fake",
    "guest", "ipad", "iphone", "laptop", "linux", "login", "mobile",
    "noname", "phone", "placeholder", "qa", "robot", "root", "script",
    "server", "signup", "simulator", "smartphone", "system", "tablet",
    "temp", "temporary", "test", "tester", "testing", "unknown", "user",
    "username", "visitor", "windows",
}
_SUSPICIOUS_COMPACT = {
    "androiddevice", "anonymoususer", "checkingaccount", "checkingsystem",
    "deviceuser", "emulatoruser", "guestuser", "iphonedevice",
    "mobiledevice", "mobilephone", "newuser", "qabot", "systemuser",
    "testaccount", "testeraccount", "testuser", "virtualdevice",
    "windowsdevice",
}
_SUSPICIOUS_GENERIC_TOKENS = {
    "another", "anonymous", "device", "dummy", "fake", "guest", "human",
    "mobile", "name", "new", "person", "proper", "random", "real", "scholar",
    "some", "student", "system", "test", "testing", "unknown", "unusual",
    "user", "account",
}

ACCOUNT_REMOVAL_WARNING = (
    "We have detected an unusual username, so we have removed your account. "
    "Please try using other proper human names. Truly, Team Alum"
)


def detect_suspicious_name(raw: Optional[str]) -> Optional[str]:
    """Return a short reason when a name looks automated/anonymous.

    ``None`` means no suspicious signal was found. The check is intentionally
    independent of :func:`validate_display_name` so the admin panel can flag
    legacy rows that were created before these rules existed.
    """
    value = unicodedata.normalize("NFKC", (raw or "")).strip()
    if not value:
        return None

    compact = _compact(value)
    if compact and compact in _SUSPICIOUS_COMPACT:
        return "system or device style name"

    # Split camelCase / PascalCase before tokenizing so "MobileDevice" and
    # "checkingSystem" are caught as well as "mobile device".
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    tokens = [
        token.casefold()
        for token in re.split(r"[\W_]+", spaced, flags=re.UNICODE)
        if token
    ]
    for token in tokens:
        if token in _SUSPICIOUS_TOKENS:
            return f"contains the non-name word '{token}'"
    if tokens and all(token in _SUSPICIOUS_GENERIC_TOKENS for token in tokens):
        return "only generic placeholder words"
    return None
_PARTICLES = {
    "van", "von", "der", "den", "de", "da", "del", "della", "bin", "ibn",
    "al", "el", "la", "le", "di", "du", "st",
}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def _is_letter(ch: str) -> bool:
    return unicodedata.category(ch)[0] in ("L", "M")


def _compact(name: str) -> str:
    return "".join(ch.casefold() for ch in name if ch.isalnum())


def username_key(name: str) -> str:
    """Canonical comparison key (storage keeps the friendly spelling)."""
    value = unicodedata.normalize("NFKC", (name or "")).strip()
    for ch in _APOSTROPHES:
        value = value.replace(ch, "'")
    for ch in _HYPHENS:
        value = value.replace(ch, "-")
    value = re.sub(r"\s+", " ", value).strip()
    return value.casefold()


def _tidy_word(word: str) -> str:
    pieces = re.split(r"(['\-])", word)
    out = []
    for piece in pieces:
        if not piece or piece in ("'", "-"):
            out.append(piece)
        elif piece.islower() or piece.isupper():
            out.append(piece[:1].upper() + piece[1:].lower())
        else:
            out.append(piece)
    return "".join(out)


def tidy_display_name(name: str) -> str:
    """Capitalise simple all-lower/all-upper input without mangling McDonald."""
    value = unicodedata.normalize("NFKC", (name or "")).strip()
    value = re.sub(r"\s+", " ", value)
    for ch in _APOSTROPHES:
        value = value.replace(ch, "'")
    for ch in _HYPHENS:
        value = value.replace(ch, "-")
    words = value.split(" ")
    tidied = []
    for index, word in enumerate(words):
        if not word:
            continue
        if index > 0 and word.casefold() in _PARTICLES:
            tidied.append(word.casefold())
        else:
            tidied.append(_tidy_word(word))
    return " ".join(tidied).strip()


def validate_display_name(
    raw: Optional[str],
    *,
    max_length: int = NAME_MAX,
) -> Tuple[Optional[str], str, str]:
    """Return ``(normalized_name, error_code, friendly_message)``.

    ``error_code`` is empty when the name is valid.
    """
    value = unicodedata.normalize("NFKC", (raw or "")).strip()
    value = re.sub(r"\s+", " ", value)
    for ch in _APOSTROPHES:
        value = value.replace(ch, "'")
    for ch in _HYPHENS:
        value = value.replace(ch, "-")

    if not value:
        return None, "required", "Could you share the name you'd like us to use?"

    if len(value) > max_length:
        return None, "too_long", f"That's a little long — please keep it under {max_length} characters."

    # Detect the *actual* problem instead of silently deleting characters.
    for ch in value:
        if ch.isdigit():
            return None, "digits", "Names don't usually include numbers — could you use letters only?"
        if ch.isspace() or ch in _APOSTROPHES or ch in _HYPHENS or ch in _PERIODS:
            continue
        if _is_letter(ch):
            continue
        return None, "invalid_chars", "Please use letters, spaces, apostrophes, hyphens, or initials for your name."

    value = value.strip(" .'’-")
    if len(value) < NAME_MIN:
        return None, "too_short", "That looks a little short — could you share the name you'd like us to use?"

    words = [w for w in value.split(" ") if w]
    if len(words) > NAME_MAX_WORDS:
        return None, "too_many_words", "That's quite a few names — please use the name you'd like us to greet you by."

    letters = [ch for ch in value if _is_letter(ch)]
    if len(letters) < NAME_MIN:
        return None, "too_short", "Could you share the name you'd like us to use? Letters work best."

    for word in words:
        core = word.strip(".'’-")
        if not core:
            return None, "invalid_chars", "Please use letters, spaces, apostrophes, hyphens, or initials for your name."
        if not any(_is_letter(ch) for ch in core):
            return None, "invalid_chars", "Please use letters, spaces, apostrophes, hyphens, or initials for your name."
        # A period is only sensible at the end of an initial ("A."), not in
        # the middle of a word ("A..B") or as decoration.
        if "." in core:
            return None, "invalid_chars", "Please use letters, spaces, apostrophes, hyphens, or initials for your name."
        if "--" in word or "''" in word:
            return None, "invalid_chars", "Please use letters, spaces, apostrophes, hyphens, or initials for your name."
        if len(core) > NAME_MAX_WORD_LEN:
            return None, "too_long", "One of those names is a little long — could you shorten it?"

    # Initials alone ("A B") are not enough to greet someone by.
    if all(len(re.sub(r"[^0-9A-Za-z\u0080-\uffff]", "", w)) <= 1 for w in words):
        return None, "too_short", "Could you share a little more of your name so we can greet you properly?"

    compact = _compact(value)
    if not compact or len(compact) < NAME_MIN:
        return None, "too_short", "Could you share the name you'd like us to use?"

    if compact in _RESERVED_COMPACT or compact.startswith(_RESERVED_PREFIXES):
        return None, "reserved", "That name belongs to the Team Alum crew — could you pick a different one for yourself?"
    if compact in _PLACEHOLDER_COMPACT:
        return None, "placeholder", "Please use the name you'd like us to greet you by — not a placeholder."
    suspicious_reason = detect_suspicious_name(value)
    if suspicious_reason:
        return None, "suspicious", "Please use a proper human name - this looks like a system, device, test, or anonymous name."
    if any(fragment in compact for fragment in _KEYBOARD_FRAGMENTS):
        return None, "not_name", "That doesn't look like a human name — could you use your real name?"
    if len(set(compact)) < 2:
        return None, "not_name", "That doesn't look like a human name — could you use your real name?"
    if re.search(r"(.)\1{3,}", compact):
        return None, "not_name", "That doesn't look like a human name — could you use your real name?"

    return tidy_display_name(value), "", ""


def is_valid_email(email: Optional[str]) -> bool:
    value = (email or "").strip()
    return bool(value) and len(value) <= 254 and bool(_EMAIL_RE.match(value))


def derive_display_name(email: str) -> str:
    """Best-effort friendly name from an email local-part."""
    local = (email or "").split("@", 1)[0]
    local = re.sub(r"\d+", " ", local)
    local = re.sub(r"[._+\-]+", " ", local)
    candidate = tidy_display_name(local)
    name, code, _ = validate_display_name(candidate)
    if not code:
        return name or candidate
    return "New Member"


def synthetic_email_for_name(name: str) -> str:
    """Server-generated address for name-only accounts.

    A random suffix keeps a name-only account from ever colliding with a real
    mailbox or another user's synthetic address.
    """
    import uuid

    slug = "".join(ch for ch in username_key(name) if ch.isalnum())[:24] or "scholar"
    return f"{slug}.{uuid.uuid4().hex[:10]}@users.alumni.ai"
