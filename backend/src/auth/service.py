import json
import secrets
import sqlite3
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request

from src import app_settings
from src.config import settings
from src.database import DBDep
from src.users import service as users_service

from .exceptions import NotAuthenticated

CODE_TTL = timedelta(minutes=5)
MAX_ATTEMPTS = 5
SESSION_TTL = timedelta(days=30)
SESSION_COOKIE_NAME = "session"

_pending_codes: dict[str, dict] = {}
_pending_codes_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(UTC)


def request_code_if_email_known(con: sqlite3.Connection, email: str) -> None:
    email = email.strip().lower()
    if users_service.get_by_email(con, email) is None:
        return

    code = f"{secrets.randbelow(1_000_000):06d}"
    with _pending_codes_lock:
        _pending_codes[email] = {"code": code, "expires_at": _now() + CODE_TTL, "attempts": 0}
    _send_email(con, email, code)


def verify_code(email: str, code: str) -> bool:
    email = email.strip().lower()
    with _pending_codes_lock:
        pending = _pending_codes.get(email)
        if pending is None:
            return False
        if _now() > pending["expires_at"]:
            del _pending_codes[email]
            return False
        if pending["attempts"] >= MAX_ATTEMPTS:
            del _pending_codes[email]
            return False

        pending["attempts"] += 1
        if secrets.compare_digest(code.strip(), pending["code"]):
            del _pending_codes[email]
            return True
        return False


def _send_email(con: sqlite3.Connection, to_addr: str, code: str) -> None:
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
            "Authorization": f"Bearer {app_settings.get(con).resend_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "YourSpotifyData/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Resend API error {e.code}: {e.read().decode()}") from e


def create_session(con: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = _now()
    con.execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, user_id, now.isoformat(), (now + SESSION_TTL).isoformat()),
    )
    con.commit()
    return token


def delete_session(con: sqlite3.Connection, token: str) -> None:
    con.execute("DELETE FROM sessions WHERE token = ?", (token,))
    con.commit()


def get_current_user(request: Request, con: sqlite3.Connection) -> sqlite3.Row:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise NotAuthenticated()
    row = con.execute(
        "SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id "
        "WHERE sessions.token = ? AND sessions.expires_at > ?",
        (token, _now().isoformat()),
    ).fetchone()
    if row is None:
        raise NotAuthenticated()
    return row


def is_logged_in(request: Request, con: sqlite3.Connection) -> bool:
    try:
        get_current_user(request, con)
        return True
    except NotAuthenticated:
        return False


def require_auth(request: Request, con: DBDep) -> None:
    get_current_user(request, con)


def can_write(request: Request, con: sqlite3.Connection, username: str) -> bool:
    try:
        user = get_current_user(request, con)
    except NotAuthenticated:
        return False
    return user["role"] == "owner" or user["username"] == username


def require_write_access(username: str, request: Request, con: DBDep) -> sqlite3.Row:
    user = get_current_user(request, con)
    if user["role"] != "owner" and user["username"] != username:
        raise HTTPException(status_code=403, detail="Not allowed")
    return user


def require_admin(username: str, request: Request, con: DBDep) -> sqlite3.Row:
    user = get_current_user(request, con)
    if user["role"] != "owner" or user["username"] != username:
        raise HTTPException(status_code=403, detail="Not allowed")
    return user
