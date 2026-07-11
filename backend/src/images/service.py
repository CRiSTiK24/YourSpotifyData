import asyncio
import base64
import datetime
import json
import logging
import sqlite3
import time
import urllib.error
import urllib.request

from src.config import settings
from src.database import get_connection

TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"

REQUEST_DELAY = 5.0  # pacing between successful calls
IDLE_POLL_SECONDS = 60.0  # how often to re-check once nothing is missing

logger = logging.getLogger("images")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class _TokenState:
    token: str | None = None
    expiry: float = 0.0


_token_state = _TokenState()


def _refresh_token_sync() -> str:
    credentials = base64.b64encode(
        f"{settings.spotify_client_id}:{settings.spotify_client_secret}".encode()
    ).decode()
    req = urllib.request.Request(
        TOKEN_URL,
        data=b"grant_type=client_credentials",
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        payload = json.loads(resp.read())
    _token_state.token = payload["access_token"]
    _token_state.expiry = time.monotonic() + payload["expires_in"] - 60
    return _token_state.token


def _get_sync(path: str, token: str) -> tuple[int, dict | None, dict]:
    req = urllib.request.Request(f"{API_BASE}{path}", headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read()), dict(resp.headers)
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            parsed = json.loads(body) if body else None
        except json.JSONDecodeError:
            parsed = None
        return e.code, parsed, dict(e.headers)


async def _ensure_token() -> str:
    if _token_state.token is None or time.monotonic() >= _token_state.expiry:
        await asyncio.to_thread(_refresh_token_sync)
    return _token_state.token


async def _api_get(path: str) -> dict | None:
    """GET path in a worker thread (keeps the event loop free), handling
    token refresh and rate limits. Returns None on 404."""
    token = await _ensure_token()
    while True:
        status, body, headers = await asyncio.to_thread(_get_sync, path, token)
        if status == 200:
            return body
        if status == 404:
            return None
        if status == 401:
            token = await asyncio.to_thread(_refresh_token_sync)
            continue
        if status == 429:
            retry_after = int(headers.get("Retry-After", "5"))
            logger.info(
                "rate limited on %s, waiting %ss (~%.1fh)", path, retry_after, retry_after / 3600
            )
            await asyncio.sleep(retry_after + 1)
            continue
        if status >= 500:
            await asyncio.sleep(5)
            continue
        raise RuntimeError(f"Spotify API error {status} on {path}: {body}")


def _uri_to_id(uri: str | None) -> str | None:
    if not uri:
        return None
    return uri.rsplit(":", 1)[-1]


def _best_image(images: list[dict]) -> str | None:
    return images[0]["url"] if images else None


def _next_missing_album(con: sqlite3.Connection) -> tuple[str, str] | None:
    row = con.execute(
        "SELECT DISTINCT th.singer, th.album FROM track_history th "
        "LEFT JOIN album_images ai "
        "ON ai.artist_name = th.singer AND ai.album_name = th.album "
        "WHERE th.singer IS NOT NULL AND th.singer != '' "
        "AND th.album IS NOT NULL AND th.album != '' "
        "AND ai.artist_name IS NULL LIMIT 1"
    ).fetchone()
    if row:
        return row[0], row[1]
    row = con.execute(
        "SELECT la.artist_name, la.album_name FROM library_albums la "
        "LEFT JOIN album_images ai "
        "ON ai.artist_name = la.artist_name AND ai.album_name = la.album_name "
        "WHERE ai.artist_name IS NULL LIMIT 1"
    ).fetchone()
    return (row[0], row[1]) if row else None


def _next_missing_artist(con: sqlite3.Connection) -> str | None:
    row = con.execute(
        "SELECT th.singer FROM track_history th "
        "LEFT JOIN artist_images ai ON ai.artist_name = th.singer "
        "WHERE th.singer IS NOT NULL AND th.singer != '' AND ai.artist_name IS NULL LIMIT 1"
    ).fetchone()
    if row:
        return row[0]
    for table, col in [
        ("library_tracks", "artist_name"),
        ("library_albums", "artist_name"),
        ("playlist_tracks", "artist_name"),
    ]:
        row = con.execute(
            f"SELECT DISTINCT {table}.{col} FROM {table} "
            f"LEFT JOIN artist_images ai ON ai.artist_name = {table}.{col} "
            "WHERE ai.artist_name IS NULL LIMIT 1"
        ).fetchone()
        if row:
            return row[0]
    return None


def _representative_track_uri(con, artist_name, album_name=None):
    if album_name:
        row = con.execute(
            "SELECT spotify_track_uri FROM track_history "
            "WHERE singer = ? AND album = ? AND spotify_track_uri IS NOT NULL LIMIT 1",
            (artist_name, album_name),
        ).fetchone()
        if row:
            return row[0]
    row = con.execute(
        "SELECT spotify_track_uri FROM track_history "
        "WHERE singer = ? AND spotify_track_uri IS NOT NULL LIMIT 1",
        (artist_name,),
    ).fetchone()
    return row[0] if row else None


def _upsert_album(con, artist_name, album_name, spotify_album_id, image_url):
    con.execute(
        """
        INSERT INTO album_images (artist_name, album_name, spotify_album_id, image_url, fetched_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(artist_name, album_name) DO UPDATE SET
            spotify_album_id = excluded.spotify_album_id,
            image_url = excluded.image_url,
            fetched_at = excluded.fetched_at
        """,
        (artist_name, album_name, spotify_album_id, image_url, _now()),
    )
    con.commit()


def _upsert_artist(con, artist_name, spotify_artist_id, image_url):
    con.execute(
        """
        INSERT INTO artist_images (artist_name, spotify_artist_id, image_url, fetched_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(artist_name) DO UPDATE SET
            spotify_artist_id = COALESCE(excluded.spotify_artist_id, artist_images.spotify_artist_id),
            image_url = COALESCE(excluded.image_url, artist_images.image_url),
            fetched_at = excluded.fetched_at
        """,
        (artist_name, spotify_artist_id, image_url, _now()),
    )
    con.commit()


def _album_uri(con, artist_name, album_name):
    row = con.execute(
        "SELECT spotify_album_uri FROM library_albums WHERE artist_name = ? AND album_name = ?",
        (artist_name, album_name),
    ).fetchone()
    return row[0] if row else None


def _artist_uri(con, artist_name):
    row = con.execute(
        "SELECT spotify_artist_uri FROM library_artists WHERE artist_name = ?", (artist_name,)
    ).fetchone()
    return row[0] if row else None


async def _fetch_one_album(con, artist_name, album_name) -> None:
    """Always writes a row (image_url NULL if nothing found), so a permanent
    miss (bad/missing id) doesn't get retried forever — same 'looked up, no
    match' convention as the rest of the schema."""
    try:
        album_id = _uri_to_id(_album_uri(con, artist_name, album_name))
        data = await _api_get(f"/albums/{album_id}") if album_id else None
        if data:
            _upsert_album(con, artist_name, album_name, data["id"], _best_image(data["images"]))
            return

        track_id = _uri_to_id(_representative_track_uri(con, artist_name, album_name))
        track = await _api_get(f"/tracks/{track_id}") if track_id else None
        if track and track.get("album"):
            alb = track["album"]
            _upsert_album(con, artist_name, album_name, alb["id"], _best_image(alb["images"]))
        else:
            _upsert_album(con, artist_name, album_name, None, None)
    except Exception:
        logger.exception("failed fetching album %s - %s", artist_name, album_name)
        _upsert_album(con, artist_name, album_name, None, None)


async def _fetch_one_artist(con, artist_name) -> None:
    try:
        artist_id = _uri_to_id(_artist_uri(con, artist_name))

        if not artist_id:
            track_id = _uri_to_id(_representative_track_uri(con, artist_name))
            track = await _api_get(f"/tracks/{track_id}") if track_id else None
            if track:
                for a in track.get("artists", []):
                    if a["name"].lower() == artist_name.lower():
                        artist_id = a["id"]
                        break

        if artist_id:
            data = await _api_get(f"/artists/{artist_id}")
            if data:
                _upsert_artist(con, artist_name, data["id"], _best_image(data["images"]))
            else:
                _upsert_artist(con, artist_name, artist_id, None)
        else:
            _upsert_artist(con, artist_name, None, None)
    except Exception:
        logger.exception("failed fetching artist %s", artist_name)
        _upsert_artist(con, artist_name, None, None)


async def image_fetch_loop() -> None:
    """Runs for the lifetime of the app: finds one album or artist still
    missing cover art, fetches and writes it, then repeats. On restart there
    is nothing to resume — the only state is the db itself, so it just
    re-queries what's still missing and keeps going."""
    if not settings.spotify_client_id or not settings.spotify_client_secret:
        logger.warning("SPOTIFY_CLIENT_ID/SECRET not set, image fetch loop disabled")
        return

    con = get_connection()
    try:
        while True:
            missing_album = _next_missing_album(con)
            if missing_album:
                await _fetch_one_album(con, *missing_album)
                await asyncio.sleep(REQUEST_DELAY)
                continue

            missing_artist = _next_missing_artist(con)
            if missing_artist:
                await _fetch_one_artist(con, missing_artist)
                await asyncio.sleep(REQUEST_DELAY)
                continue

            await asyncio.sleep(IDLE_POLL_SECONDS)
    finally:
        con.close()
