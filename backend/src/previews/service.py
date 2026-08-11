import re
import sqlite3
import urllib.error
import urllib.request
from functools import lru_cache

_EMBED_URL = "https://open.spotify.com/embed/track/{track_id}"
_AUDIO_PREVIEW_RE = re.compile(r'"audioPreview":\s*{\s*"url":\s*"([^"]+)"')

_URI_LOOKUP_QUERIES = [
    "SELECT spotify_track_uri FROM track_history "
    "WHERE name = ? AND (singer = ? OR singer IS NULL) AND spotify_track_uri IS NOT NULL LIMIT 1",
    "SELECT spotify_track_uri FROM library_tracks "
    "WHERE track_name = ? AND artist_name = ? AND spotify_track_uri IS NOT NULL LIMIT 1",
    "SELECT spotify_track_uri FROM playlist_tracks "
    "WHERE track_name = ? AND artist_name = ? AND spotify_track_uri IS NOT NULL LIMIT 1",
]


def resolve_track_id(con: sqlite3.Connection, track_name: str, artist_name: str) -> str | None:
    for query in _URI_LOOKUP_QUERIES:
        row = con.execute(query, (track_name, artist_name)).fetchone()
        if row and row[0]:
            return row[0].rsplit(":", 1)[-1]
    return None


def _extract_preview_url(html: str) -> str | None:
    match = _AUDIO_PREVIEW_RE.search(html)
    return match.group(1) if match else None


@lru_cache(maxsize=2048)
def fetch_preview_url(spotify_track_id: str) -> str | None:
    req = urllib.request.Request(_EMBED_URL.format(track_id=spotify_track_id))
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8")
    except urllib.error.URLError:
        return None
    return _extract_preview_url(html)
