import json
import secrets
import sqlite3
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta

from fastapi import Request

from src.config import settings
from src.database import DBDep

from .exceptions import NotAuthenticated

CODE_TTL = timedelta(minutes=5)
MAX_ATTEMPTS = 5
SESSION_TTL = timedelta(days=30)
SESSION_COOKIE_NAME = "session"

# Single pending login code at a time — this app has exactly one authorized
# user, so there's no need for per-email state.
_pending: dict | None = None


def _now() -> datetime:
    return datetime.now(UTC)


def request_code(email: str) -> None:
    """Send a login code if the email matches the configured owner. Always
    behaves the same regardless of match, so the caller can show an
    identical response either way (avoids confirming which email is valid)."""
    global _pending
    if not settings.allowed_email or email.strip().lower() != settings.allowed_email.lower():
        return

    code = f"{secrets.randbelow(1_000_000):06d}"
    _pending = {"code": code, "expires_at": _now() + CODE_TTL, "attempts": 0}
    _send_email(email, code)


def verify_code(code: str) -> bool:
    """Check the submitted code against the pending one. Returns True and
    clears pending state on success."""
    global _pending
    if _pending is None:
        return False
    if _now() > _pending["expires_at"]:
        _pending = None
        return False
    if _pending["attempts"] >= MAX_ATTEMPTS:
        _pending = None
        return False

    _pending["attempts"] += 1
    if secrets.compare_digest(code.strip(), _pending["code"]):
        _pending = None
        return True
    return False


def _send_email(to_addr: str, code: str) -> None:
    payload = json.dumps(
        {
            "from": settings.resend_from,
            "to": [to_addr],
            "subject": "Your Spotify Data — login code",
            "text": f"Your login code is {code}. It expires in 5 minutes.",
        }
    ).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "YourSpotifyData/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Resend API error {e.code}: {e.read().decode()}") from e


def create_session(con: sqlite3.Connection) -> str:
    token = secrets.token_urlsafe(32)
    now = _now()
    con.execute(
        "INSERT INTO sessions (token, created_at, expires_at) VALUES (?, ?, ?)",
        (token, now.isoformat(), (now + SESSION_TTL).isoformat()),
    )
    con.commit()
    return token


def session_valid(con: sqlite3.Connection, token: str) -> bool:
    row = con.execute("SELECT expires_at FROM sessions WHERE token = ?", (token,)).fetchone()
    if row is None:
        return False
    return _now() <= datetime.fromisoformat(row["expires_at"])


def delete_session(con: sqlite3.Connection, token: str) -> None:
    con.execute("DELETE FROM sessions WHERE token = ?", (token,))
    con.commit()


def require_auth(request: Request, con: DBDep) -> None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token or not session_valid(con, token):
        raise NotAuthenticated()
