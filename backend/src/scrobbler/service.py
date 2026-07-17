import asyncio
import json
import logging
import secrets
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64encode
from datetime import UTC, datetime, timedelta

from src.config import settings
from src.database import get_connection

from .exceptions import NotConnected

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
RECENTLY_PLAYED_URL = "https://api.spotify.com/v1/me/player/recently-played?limit=50"
SCOPE = "user-read-recently-played playlist-read-private user-library-read user-follow-read"

# CSRF state for the OAuth redirect — short-lived and single-user, so a
# module-level slot (mirroring src.auth.service._pending) is enough.
_pending_state: str | None = None


def _now() -> datetime:
    return datetime.now(UTC)


def _basic_auth_header() -> str:
    credentials = f"{settings.spotify_client_id}:{settings.spotify_client_secret}".encode()
    return f"Basic {b64encode(credentials).decode()}"


def start_authorization() -> str:
    """Generates and remembers a CSRF state, returning the URL to redirect
    the user to for Spotify's consent screen."""
    global _pending_state
    _pending_state = secrets.token_urlsafe(24)
    params = {
        "client_id": settings.spotify_client_id,
        "response_type": "code",
        "redirect_uri": settings.spotify_redirect_uri,
        "scope": SCOPE,
        "state": _pending_state,
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def verify_state(state: str) -> bool:
    global _pending_state
    match = _pending_state is not None and secrets.compare_digest(state, _pending_state)
    _pending_state = None
    return match


def _post_token_request(data: dict) -> dict:
    req = urllib.request.Request(
        TOKEN_URL,
        data=urllib.parse.urlencode(data).encode(),
        method="POST",
        headers={
            "Authorization": _basic_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Spotify token request failed ({e.code}): {e.read().decode()}") from e


def exchange_code(con: sqlite3.Connection, code: str) -> None:
    payload = _post_token_request(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.spotify_redirect_uri,
        }
    )
    now = _now()
    con.execute(
        "INSERT INTO scrobbler_tokens "
        "(id, access_token, refresh_token, expires_at, connected_at) "
        "VALUES (1, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET "
        "access_token = excluded.access_token, "
        "refresh_token = excluded.refresh_token, "
        "expires_at = excluded.expires_at, "
        "connected_at = excluded.connected_at",
        (
            payload["access_token"],
            payload["refresh_token"],
            (now + timedelta(seconds=payload["expires_in"] - 60)).isoformat(),
            now.isoformat(),
        ),
    )
    con.commit()


def get_status(con: sqlite3.Connection) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM scrobbler_tokens WHERE id = 1").fetchone()


def disconnect(con: sqlite3.Connection) -> None:
    con.execute("DELETE FROM scrobbler_tokens WHERE id = 1")
    con.commit()


def _refresh_access_token(con: sqlite3.Connection, refresh_token: str) -> str:
    payload = _post_token_request(
        {"grant_type": "refresh_token", "refresh_token": refresh_token}
    )
    now = _now()
    new_refresh_token = payload.get("refresh_token", refresh_token)
    con.execute(
        "UPDATE scrobbler_tokens SET access_token = ?, refresh_token = ?, expires_at = ? "
        "WHERE id = 1",
        (
            payload["access_token"],
            new_refresh_token,
            (now + timedelta(seconds=payload["expires_in"] - 60)).isoformat(),
        ),
    )
    con.commit()
    return payload["access_token"]


def _ensure_access_token(con: sqlite3.Connection) -> str:
    row = get_status(con)
    if row is None:
        raise NotConnected()
    if _now() < datetime.fromisoformat(row["expires_at"]):
        return row["access_token"]
    return _refresh_access_token(con, row["refresh_token"])


def _fetch_recently_played(access_token: str) -> list[dict]:
    req = urllib.request.Request(
        RECENTLY_PLAYED_URL, headers={"Authorization": f"Bearer {access_token}"}
    )
    with urllib.request.urlopen(req) as resp:
        payload = json.loads(resp.read())
    return payload.get("items", [])


def _save_new_plays(con: sqlite3.Connection, items: list[dict]) -> int:
    """Same incremental rule as processors/StreamingHistoryProcessor.py: only
    insert plays newer than what's already stored, so overlapping polls (and
    a manual GDPR re-upload later) never duplicate history."""
    last_max = con.execute("SELECT MAX(time) FROM track_history").fetchone()[0]
    new_rows = []
    for item in items:
        played_at = item["played_at"]
        if last_max is not None and played_at <= last_max:
            continue
        track = item["track"]
        artists = track.get("artists") or []
        new_rows.append(
            (
                track["name"],
                artists[0]["name"] if artists else None,
                track["album"]["name"] if track.get("album") else None,
                played_at,
                track.get("uri"),
            )
        )
    con.executemany(
        "INSERT INTO track_history (name, singer, album, time, spotify_track_uri) "
        "VALUES (?, ?, ?, ?, ?)",
        new_rows,
    )
    con.commit()
    return len(new_rows)


def poll_once(con: sqlite3.Connection) -> int:
    """Runs one poll cycle: refresh token if needed, fetch recently-played,
    insert new plays, and record the outcome for the /scrobbler status page.
    Raises NotConnected if no account is linked yet."""
    access_token = _ensure_access_token(con)
    try:
        items = _fetch_recently_played(access_token)
        new_count = _save_new_plays(con, items)
    except Exception as e:
        con.execute(
            "UPDATE scrobbler_tokens SET last_poll_at = ?, last_error = ? WHERE id = 1",
            (_now().isoformat(), str(e)[:2000]),
        )
        con.commit()
        raise
    con.execute(
        "UPDATE scrobbler_tokens SET last_poll_at = ?, last_poll_new = ?, last_error = NULL "
        "WHERE id = 1",
        (_now().isoformat(), new_count),
    )
    con.commit()
    return new_count


async def poll_loop() -> None:
    """Background task started from the app lifespan. Runs forever, sleeping
    scrobbler_poll_seconds between polls; a poll failure (e.g. not connected
    yet, or a transient Spotify API error) is logged and retried next tick
    rather than killing the loop."""
    logger = logging.getLogger("scrobbler")
    while True:
        await asyncio.sleep(settings.scrobbler_poll_seconds)
        con = get_connection()
        try:
            if get_status(con) is not None:
                poll_once(con)
        except NotConnected:
            pass
        except Exception:
            logger.exception("scrobbler poll failed")
        finally:
            con.close()
