#!/usr/bin/env python3
"""Resolve album/artist cover art via the Spotify Web API (Client Credentials
flow) and cache the image URLs in SpotifyData.db.

Uses only real Spotify IDs already captured from the GDPR export (track/
album/artist URIs) — one GET per distinct album/artist, no /search calls.
Safe to re-run: already-cached (artist, album) / artist rows are skipped.

Requires SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET, either exported in the
environment or set in a `.env` file at the repo root.
"""
import base64
import datetime
import json
import os
import sqlite3
import time
import urllib.error
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "spotifyProcessed")
DB_PATH = os.path.join(PROCESSED_DIR, "SpotifyData.db")
SCHEMA_PATH = os.path.join(PROCESSED_DIR, "schema.sql")
ENV_PATH = os.path.join(BASE_DIR, ".env")
LOCK_PATH = os.path.join(PROCESSED_DIR, ".image_fetch.lock")

TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"

REQUEST_DELAY = 5.0
MAX_RETRIES = 5
COMMIT_EVERY = 20


def load_dotenv(path):
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key and key not in os.environ:
                os.environ[key] = value.strip().strip("'\"")


class SpotifyClient:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = None
        self._token_expiry = 0

    def _refresh_token(self):
        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
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
        self._token = payload["access_token"]
        self._token_expiry = time.monotonic() + payload["expires_in"] - 60

    def _ensure_token(self):
        if self._token is None or time.monotonic() >= self._token_expiry:
            self._refresh_token()

    def get(self, path):
        """GET a Spotify API path, returning the parsed JSON body or None on 404."""
        self._ensure_token()
        url = f"{API_BASE}{path}"
        for attempt in range(MAX_RETRIES):
            req = urllib.request.Request(
                url, headers={"Authorization": f"Bearer {self._token}"}
            )
            try:
                with urllib.request.urlopen(req) as resp:
                    time.sleep(REQUEST_DELAY)
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    time.sleep(REQUEST_DELAY)
                    return None
                if e.code == 401:
                    self._refresh_token()
                    continue
                if e.code == 429:
                    retry_after = int(e.headers.get("Retry-After", "5"))
                    print(f"  rate limited, waiting {retry_after}s (~{retry_after / 3600:.1f}h)...")
                    time.sleep(retry_after + 1)
                    continue
                if e.code >= 500:
                    time.sleep(2**attempt)
                    continue
                raise
            except urllib.error.URLError:
                time.sleep(2**attempt)
                continue
        print(f"  giving up on {path} after {MAX_RETRIES} attempts")
        return None


def uri_to_id(uri):
    if not uri:
        return None
    return uri.rsplit(":", 1)[-1]


def gather_albums(con):
    """Return {(artist_name, album_name): spotify_album_uri | None} for every
    album seen in play history or the liked-albums library."""
    albums = {}
    for singer, album in con.execute(
        "SELECT DISTINCT singer, album FROM track_history "
        "WHERE singer IS NOT NULL AND singer != '' AND album IS NOT NULL AND album != ''"
    ):
        albums.setdefault((singer, album), None)
    for artist_name, album_name, uri in con.execute(
        "SELECT artist_name, album_name, spotify_album_uri FROM library_albums"
    ):
        albums[(artist_name, album_name)] = uri
    return albums


def gather_artists(con):
    """Return {artist_name: spotify_artist_uri | None} for every artist seen
    anywhere in the library."""
    artists = {}
    for (singer,) in con.execute(
        "SELECT DISTINCT singer FROM track_history WHERE singer IS NOT NULL AND singer != ''"
    ):
        artists.setdefault(singer, None)
    for table, col in [
        ("library_tracks", "artist_name"),
        ("library_albums", "artist_name"),
        ("playlist_tracks", "artist_name"),
    ]:
        for (name,) in con.execute(f"SELECT DISTINCT {col} FROM {table}"):
            artists.setdefault(name, None)
    for name, uri in con.execute("SELECT artist_name, spotify_artist_uri FROM library_artists"):
        artists[name] = uri
    return artists


def already_cached(con, table, key_cols, key_values):
    where = " AND ".join(f"{c} = ?" for c in key_cols)
    row = con.execute(f"SELECT 1 FROM {table} WHERE {where}", key_values).fetchone()
    return row is not None


def representative_track_uri(con, artist_name, album_name=None):
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


def upsert_album(con, artist_name, album_name, spotify_album_id, image_url):
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


def upsert_artist(con, artist_name, spotify_artist_id, image_url):
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


def best_image(images):
    return images[0]["url"] if images else None


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def fetch_albums(con, client, albums, known_artist_ids):
    to_fetch = [
        (artist, album, uri)
        for (artist, album), uri in albums.items()
        if not already_cached(con, "album_images", ["artist_name", "album_name"], [artist, album])
    ]
    print(f"Fetching {len(to_fetch)} albums (of {len(albums)} total)...")

    done = 0
    for artist_name, album_name, album_uri in to_fetch:
        album_id = uri_to_id(album_uri)
        data = None

        if album_id:
            data = client.get(f"/albums/{album_id}")
            if data:
                for a in data.get("artists", []):
                    known_artist_ids.setdefault(a["name"], a["id"])
                upsert_album(con, artist_name, album_name, data["id"], best_image(data["images"]))

        if not data:
            track_uri = representative_track_uri(con, artist_name, album_name)
            track_id = uri_to_id(track_uri)
            track = client.get(f"/tracks/{track_id}") if track_id else None
            if track and track.get("album"):
                alb = track["album"]
                for a in track.get("artists", []):
                    known_artist_ids.setdefault(a["name"], a["id"])
                upsert_album(con, artist_name, album_name, alb["id"], best_image(alb["images"]))
            else:
                upsert_album(con, artist_name, album_name, None, None)

        done += 1
        if done % COMMIT_EVERY == 0:
            con.commit()
            print(f"  {done}/{len(to_fetch)} albums processed")
    con.commit()
    print(f"  {done}/{len(to_fetch)} albums processed")


def fetch_artists(con, client, artists, known_artist_ids):
    to_fetch = [
        (name, uri)
        for name, uri in artists.items()
        if not already_cached(con, "artist_images", ["artist_name"], [name])
    ]
    print(f"Fetching {len(to_fetch)} artists (of {len(artists)} total)...")

    done = 0
    for artist_name, artist_uri in to_fetch:
        artist_id = uri_to_id(artist_uri) or known_artist_ids.get(artist_name)

        if not artist_id:
            track_uri = representative_track_uri(con, artist_name)
            track_id = uri_to_id(track_uri)
            track = client.get(f"/tracks/{track_id}") if track_id else None
            if track:
                for a in track.get("artists", []):
                    if a["name"].lower() == artist_name.lower():
                        artist_id = a["id"]
                        break

        if artist_id:
            data = client.get(f"/artists/{artist_id}")
            if data:
                upsert_artist(con, artist_name, data["id"], best_image(data["images"]))
            else:
                upsert_artist(con, artist_name, artist_id, None)
        else:
            upsert_artist(con, artist_name, None, None)

        done += 1
        if done % COMMIT_EVERY == 0:
            con.commit()
            print(f"  {done}/{len(to_fetch)} artists processed")
    con.commit()
    print(f"  {done}/{len(to_fetch)} artists processed")


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _acquire_lock():
    """Callers (app startup, upload, scrobbler poll) may all trigger this
    script concurrently; only one instance should touch the db at a time.
    Stale locks (owning pid no longer alive, e.g. after a crash) are
    reclaimed rather than blocking forever."""
    if os.path.exists(LOCK_PATH):
        with open(LOCK_PATH) as f:
            content = f.read().strip()
        if content.isdigit() and _pid_alive(int(content)):
            return False
    with open(LOCK_PATH, "w") as f:
        f.write(str(os.getpid()))
    return True


def _release_lock():
    try:
        os.remove(LOCK_PATH)
    except FileNotFoundError:
        pass


def main():
    if not _acquire_lock():
        print("Another image fetch is already running, skipping.")
        return

    try:
        load_dotenv(ENV_PATH)
        client_id = os.environ.get("SPOTIFY_CLIENT_ID")
        client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise SystemExit(
                "SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set "
                f"(export them or add them to {ENV_PATH})"
            )

        con = sqlite3.connect(DB_PATH)
        with open(SCHEMA_PATH) as f:
            con.executescript(f.read())

        client = SpotifyClient(client_id, client_secret)
        known_artist_ids = {}

        try:
            albums = gather_albums(con)
            fetch_albums(con, client, albums, known_artist_ids)

            artists = gather_artists(con)
            fetch_artists(con, client, artists, known_artist_ids)
        finally:
            con.close()

        print(f"\nSaved to {DB_PATH}")
    finally:
        _release_lock()


if __name__ == "__main__":
    main()
