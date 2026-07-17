import asyncio
import importlib.util
import json
import logging
import os
import sqlite3
import time
import urllib.error
import urllib.request

from src.config import settings
from src.database import get_connection

from . import service as scrobbler_service
from .exceptions import NotConnected

logger = logging.getLogger("library_sync")

API_BASE = "https://api.spotify.com/v1"

# The GDPR-export processors (processors/*.py) already implement the
# upsert-and-prune sync logic this needs (playlists matched by name with
# tracks replaced, library items matched by key with removals pruned). They
# live outside the backend/src package (they're invoked as standalone
# scripts by the /upload flow), so they're loaded here by file path rather
# than a normal import, to reuse that logic instead of duplicating it.
_PROCESSORS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "processors"
)


def _load_processor(name: str):
    path = os.path.join(_PROCESSORS_DIR, f"{name}.py")
    spec = importlib.util.spec_from_file_location(f"processors.{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_playlist_processor = _load_processor("PlaylistProcessor")
_library_processor = _load_processor("YourLibraryProcessor")


def _api_get(access_token: str, url: str) -> dict:
    while True:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(int(e.headers.get("Retry-After", "1")))
                continue
            raise


def _paginate(access_token: str, url: str) -> list[dict]:
    items = []
    while url:
        data = _api_get(access_token, url)
        items.extend(data.get("items", []))
        url = data.get("next")
    return items


def _paginate_cursor(access_token: str, url: str) -> list[dict]:
    items = []
    while url:
        block = _api_get(access_token, url)["artists"]
        items.extend(block["items"])
        url = block.get("next")
    return items


def _fetch_playlists(con: sqlite3.Connection, access_token: str) -> list[dict]:
    """Fetching every track of every playlist on every run is the bulk of
    this sync's request volume. Spotify's playlist snapshot_id changes
    whenever a playlist's contents change, so a playlist whose snapshot_id
    still matches what's stored from last sync is skipped entirely (no
    tracks call at all) - same approach used by other Spotify sync tools."""
    _playlist_processor.ensure_schema_columns(con)
    known_snapshots = _playlist_processor.get_snapshot_ids(con)

    playlists = []
    for pl in _paginate(access_token, f"{API_BASE}/me/playlists?limit=50"):
        if pl is None:
            continue
        entry = {
            "name": pl["name"],
            "spotifyPlaylistId": pl["id"],
            "spotifySnapshotId": pl.get("snapshot_id"),
        }
        if pl.get("snapshot_id") is not None and known_snapshots.get(pl["name"]) == pl["snapshot_id"]:
            entry["unchanged"] = True
            playlists.append(entry)
            continue

        tracks = []
        for item in _paginate(access_token, f"{API_BASE}/playlists/{pl['id']}/tracks?limit=100"):
            track = item.get("track")
            if not track or track.get("is_local"):
                continue
            artists = track.get("artists") or []
            tracks.append(
                {
                    "trackName": track["name"],
                    "artistName": artists[0]["name"] if artists else "",
                    "trackUri": track.get("uri"),
                }
            )
        entry["tracks"] = tracks
        playlists.append(entry)
    return playlists


def _fetch_liked_tracks(access_token: str) -> list[dict]:
    tracks = []
    for item in _paginate(access_token, f"{API_BASE}/me/tracks?limit=50"):
        track = item.get("track")
        if not track:
            continue
        artists = track.get("artists") or []
        tracks.append(
            {
                "track_name": track["name"],
                "artist_name": artists[0]["name"] if artists else "",
                "uri": track.get("uri"),
            }
        )
    return tracks


def _fetch_liked_albums(access_token: str) -> list[dict]:
    albums = []
    for item in _paginate(access_token, f"{API_BASE}/me/albums?limit=50"):
        album = item.get("album")
        if not album:
            continue
        artists = album.get("artists") or []
        albums.append(
            {
                "album_name": album["name"],
                "artist_name": artists[0]["name"] if artists else "",
                "uri": album.get("uri"),
            }
        )
    return albums


def _fetch_followed_artists(access_token: str) -> list[dict]:
    return [
        {"artist_name": a["name"], "uri": a.get("uri")}
        for a in _paginate_cursor(access_token, f"{API_BASE}/me/following?type=artist&limit=50")
    ]


def sync_once(con: sqlite3.Connection) -> dict:
    """Pulls the account's current playlists, liked songs, liked albums and
    followed artists from the Spotify Web API and syncs them into the same
    tables the GDPR export upload fills in, via the same processor
    save_to_db functions - so this is the "live" equivalent of periodically
    re-uploading the export zip. Every fetch here always returns the full,
    current set (the Spotify API doesn't offer a delta/changes-since
    endpoint), so pruning of removed items is always safe."""
    access_token = scrobbler_service._ensure_access_token(con)

    playlists = _fetch_playlists(con, access_token)
    counts = _playlist_processor.save_to_db(con, playlists, prune_missing=True)

    tracks = _fetch_liked_tracks(access_token)
    albums = _fetch_liked_albums(access_token)
    artists = _fetch_followed_artists(access_token)
    counts.update(_library_processor.save_to_db(con, tracks, albums, artists))

    return counts


async def sync_loop() -> None:
    """Background task started from the app lifespan, mirroring
    scrobbler.service.poll_loop but for the much heavier library sync."""
    while True:
        await asyncio.sleep(settings.library_sync_poll_seconds)
        con = get_connection()
        try:
            if scrobbler_service.get_status(con) is not None:
                counts = sync_once(con)
                logger.info("library sync complete: %s", counts)
        except NotConnected:
            pass
        except Exception:
            logger.exception("library sync failed")
        finally:
            con.close()
