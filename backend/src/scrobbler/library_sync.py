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

from . import service as scrobbler_service
from .loop import run_periodic

logger = logging.getLogger("library_sync")

API_BASE = "https://api.spotify.com/v1"

_PROCESSORS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "processors"
)


def _load_processor_module_by_path(name: str):
    path = os.path.join(_PROCESSORS_DIR, f"{name}.py")
    spec = importlib.util.spec_from_file_location(f"processors.{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_playlist_processor = _load_processor_module_by_path("PlaylistProcessor")
_library_processor = _load_processor_module_by_path("YourLibraryProcessor")


def ensure_migrations(con: sqlite3.Connection) -> None:
    _playlist_processor.ensure_schema_columns(con)


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


def _fetch_current_user_id(access_token: str) -> str:
    return _api_get(access_token, f"{API_BASE}/me")["id"]


def _fetch_owned_playlists(
    con: sqlite3.Connection, access_token: str, my_user_id: str, user_id: int
) -> list[dict]:
    _playlist_processor.ensure_schema_columns(con)
    known_snapshots = _playlist_processor.get_snapshot_ids(con, user_id)

    playlists = []
    for pl in _paginate(access_token, f"{API_BASE}/me/playlists?limit=50"):
        if pl is None:
            continue
        owner = pl.get("owner") or {}
        if owner.get("id") != my_user_id:
            continue
        images = pl.get("images") or []
        entry = {
            "name": pl["name"],
            "spotifyPlaylistId": pl["id"],
            "spotifySnapshotId": pl.get("snapshot_id"),
            "imageUrl": images[0]["url"] if images else None,
            "description": pl.get("description") or None,
        }
        if (
            pl.get("snapshot_id") is not None
            and known_snapshots.get(pl["name"]) == pl["snapshot_id"]
        ):
            entry["unchanged"] = True
            playlists.append(entry)
            continue

        tracks = []
        for item in _paginate(access_token, f"{API_BASE}/playlists/{pl['id']}/tracks?limit=100"):
            track = item.get("track")
            if not track or track.get("is_local"):
                continue
            if track["name"] == scrobbler_service.UNKNOWN_TRACK_NAME:
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
        if track["name"] == scrobbler_service.UNKNOWN_TRACK_NAME:
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


def set_playlist_description_via_spotify_api(
    con: sqlite3.Connection, user_id: int, spotify_playlist_id: str, description: str
) -> None:
    access_token = scrobbler_service.ensure_access_token(con, user_id)
    body = json.dumps({"description": description}).encode()
    req = urllib.request.Request(
        f"{API_BASE}/playlists/{spotify_playlist_id}/details",
        data=body,
        method="PUT",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req):
        pass


def sync_once(con: sqlite3.Connection, user_id: int) -> dict:
    access_token = scrobbler_service.ensure_access_token(con, user_id)
    my_user_id = _fetch_current_user_id(access_token)

    playlists = _fetch_owned_playlists(con, access_token, my_user_id, user_id)
    counts = _playlist_processor.save_to_db(con, playlists, user_id, remove_missing=True)

    tracks = _fetch_liked_tracks(access_token)
    albums = _fetch_liked_albums(access_token)
    artists = _fetch_followed_artists(access_token)
    counts.update(_library_processor.save_to_db(con, tracks, albums, artists, user_id))

    return counts


async def _sync_and_log(con: sqlite3.Connection, user_id: int) -> None:
    counts = await asyncio.to_thread(sync_once, con, user_id)
    logger.info("library sync complete for user %d: %s", user_id, counts)


async def sync_loop() -> None:
    await run_periodic(
        _sync_and_log,
        interval_seconds=settings.library_sync_poll_seconds,
        logger=logger,
        connected_user_ids=scrobbler_service.connected_user_ids,
    )
