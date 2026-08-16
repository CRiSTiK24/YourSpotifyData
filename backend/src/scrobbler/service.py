import asyncio
import json
import logging
import secrets
import sqlite3
import threading
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64encode
from datetime import UTC, datetime, timedelta

from src import app_settings
from src.config import settings
from src.users import service as users_service

from .exceptions import NotConnected
from .loop import run_periodic

logger = logging.getLogger("scrobbler")

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
RECENTLY_PLAYED_URL = "https://api.spotify.com/v1/me/player/recently-played?limit=50"
SCOPE = (
    "user-read-recently-played playlist-read-private user-library-read user-follow-read "
    "playlist-modify-public playlist-modify-private"
)

_pending_oauth_states: dict[str, int] = {}
_pending_oauth_states_lock = threading.Lock()

UNKNOWN_TRACK_NAME = "Unknown Track"


def _now() -> datetime:
    return datetime.now(UTC)


def _basic_auth_header(con: sqlite3.Connection) -> str:
    eff = app_settings.get(con)
    credentials = f"{eff.spotify_client_id}:{eff.spotify_client_secret}".encode()
    return f"Basic {b64encode(credentials).decode()}"


def ensure_user_scoped_schema(con: sqlite3.Connection) -> None:
    cols = [row["name"] for row in con.execute("PRAGMA table_info(scrobbler_tokens)")]
    if "user_id" in cols:
        return

    owner = users_service.get_owner(con)
    con.execute(
        "CREATE TABLE scrobbler_tokens_new ("
        "user_id INTEGER PRIMARY KEY REFERENCES users(id), "
        "access_token TEXT NOT NULL, "
        "refresh_token TEXT NOT NULL, "
        "expires_at TEXT NOT NULL, "
        "connected_at TEXT NOT NULL, "
        "last_poll_at TEXT, "
        "last_poll_new INTEGER, "
        "last_error TEXT)"
    )
    existing = con.execute("SELECT * FROM scrobbler_tokens WHERE id = 1").fetchone()
    if existing is not None:
        con.execute(
            "INSERT INTO scrobbler_tokens_new "
            "(user_id, access_token, refresh_token, expires_at, connected_at, "
            "last_poll_at, last_poll_new, last_error) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                owner["id"],
                existing["access_token"],
                existing["refresh_token"],
                existing["expires_at"],
                existing["connected_at"],
                existing["last_poll_at"],
                existing["last_poll_new"],
                existing["last_error"],
            ),
        )
    con.execute("DROP TABLE scrobbler_tokens")
    con.execute("ALTER TABLE scrobbler_tokens_new RENAME TO scrobbler_tokens")
    con.commit()


def start_authorization(con: sqlite3.Connection, user_id: int) -> str:
    state = secrets.token_urlsafe(24)
    with _pending_oauth_states_lock:
        _pending_oauth_states[state] = user_id
    eff = app_settings.get(con)
    params = {
        "client_id": eff.spotify_client_id,
        "response_type": "code",
        "redirect_uri": eff.spotify_redirect_uri,
        "scope": SCOPE,
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def resolve_state(state: str) -> int | None:
    with _pending_oauth_states_lock:
        return _pending_oauth_states.pop(state, None)


def _post_token_request(con: sqlite3.Connection, data: dict) -> dict:
    req = urllib.request.Request(
        TOKEN_URL,
        data=urllib.parse.urlencode(data).encode(),
        method="POST",
        headers={
            "Authorization": _basic_auth_header(con),
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Spotify token request failed ({e.code}): {e.read().decode()}") from e


def exchange_code(con: sqlite3.Connection, user_id: int, code: str) -> None:
    payload = _post_token_request(
        con,
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": app_settings.get(con).spotify_redirect_uri,
        },
    )
    now = _now()
    con.execute(
        "INSERT INTO scrobbler_tokens "
        "(user_id, access_token, refresh_token, expires_at, connected_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET "
        "access_token = excluded.access_token, "
        "refresh_token = excluded.refresh_token, "
        "expires_at = excluded.expires_at, "
        "connected_at = excluded.connected_at",
        (
            user_id,
            payload["access_token"],
            payload["refresh_token"],
            (now + timedelta(seconds=payload["expires_in"] - 60)).isoformat(),
            now.isoformat(),
        ),
    )
    con.commit()


def get_status(con: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM scrobbler_tokens WHERE user_id = ?", (user_id,)).fetchone()


def connected_user_ids(con: sqlite3.Connection) -> list[int]:
    return [row["user_id"] for row in con.execute("SELECT user_id FROM scrobbler_tokens")]


def disconnect(con: sqlite3.Connection, user_id: int) -> None:
    con.execute("DELETE FROM scrobbler_tokens WHERE user_id = ?", (user_id,))
    con.commit()


def _refresh_access_token(con: sqlite3.Connection, user_id: int, refresh_token: str) -> str:
    payload = _post_token_request(
        con, {"grant_type": "refresh_token", "refresh_token": refresh_token}
    )
    now = _now()
    new_refresh_token = payload.get("refresh_token", refresh_token)
    con.execute(
        "UPDATE scrobbler_tokens SET access_token = ?, refresh_token = ?, expires_at = ? "
        "WHERE user_id = ?",
        (
            payload["access_token"],
            new_refresh_token,
            (now + timedelta(seconds=payload["expires_in"] - 60)).isoformat(),
            user_id,
        ),
    )
    con.commit()
    return payload["access_token"]


def ensure_access_token(con: sqlite3.Connection, user_id: int) -> str:
    row = get_status(con, user_id)
    if row is None:
        raise NotConnected()
    if _now() < datetime.fromisoformat(row["expires_at"]):
        return row["access_token"]
    return _refresh_access_token(con, user_id, row["refresh_token"])


def _fetch_recently_played(access_token: str) -> list[dict]:
    req = urllib.request.Request(
        RECENTLY_PLAYED_URL, headers={"Authorization": f"Bearer {access_token}"}
    )
    with urllib.request.urlopen(req) as resp:
        payload = json.loads(resp.read())
    return payload.get("items", [])


def _save_new_plays(con: sqlite3.Connection, user_id: int, items: list[dict]) -> int:
    last_known_played_at = con.execute(
        "SELECT MAX(time) FROM track_history WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    new_rows = []
    for item in items:
        played_at = item["played_at"]
        if last_known_played_at is not None and played_at <= last_known_played_at:
            continue
        track = item["track"]
        if track["name"] == UNKNOWN_TRACK_NAME:
            continue
        artists = track.get("artists") or []
        new_rows.append(
            (
                user_id,
                track["name"],
                artists[0]["name"] if artists else None,
                track["album"]["name"] if track.get("album") else None,
                played_at,
                track.get("uri"),
            )
        )
    con.executemany(
        "INSERT INTO track_history (user_id, name, singer, album, time, spotify_track_uri) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        new_rows,
    )
    con.commit()
    return len(new_rows)


def poll_once(con: sqlite3.Connection, user_id: int) -> int:
    access_token = ensure_access_token(con, user_id)
    try:
        items = _fetch_recently_played(access_token)
        new_count = _save_new_plays(con, user_id, items)
    except Exception as e:
        con.execute(
            "UPDATE scrobbler_tokens SET last_poll_at = ?, last_error = ? WHERE user_id = ?",
            (_now().isoformat(), str(e)[:2000], user_id),
        )
        con.commit()
        raise
    con.execute(
        "UPDATE scrobbler_tokens SET last_poll_at = ?, last_poll_new = ?, last_error = NULL "
        "WHERE user_id = ?",
        (_now().isoformat(), new_count, user_id),
    )
    con.commit()
    return new_count


async def _poll(con: sqlite3.Connection, user_id: int) -> None:
    new_count = await asyncio.to_thread(poll_once, con, user_id)
    logger.info("poll complete for user %d: %d new plays", user_id, new_count)


async def poll_loop() -> None:
    await run_periodic(
        _poll,
        interval_seconds=settings.scrobbler_poll_seconds,
        logger=logger,
        connected_user_ids=connected_user_ids,
    )
