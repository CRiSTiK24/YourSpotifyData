#!/usr/bin/env python3
import glob
import json
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
RAW_DIR = os.path.join(BASE_DIR, "data", "spotifyRaw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "spotifyProcessed")
DB_PATH = os.path.join(PROCESSED_DIR, "SpotifyData.db")
SCHEMA_PATH = os.path.join(PROCESSED_DIR, "schema.sql")


def process_playlists():
    files = sorted(glob.glob(os.path.join(RAW_DIR, "Playlist*.json")))
    return _parse_playlist_files(files), len(files) > 0


def _parse_playlist_files(files):
    playlists = []
    for path in files:
        with open(path) as f:
            data = json.load(f)
        for pl in data["playlists"]:
            tracks = [
                {
                    "trackName": item["track"]["trackName"],
                    "artistName": item["track"]["artistName"],
                    "trackUri": item["track"].get("trackUri"),
                }
                for item in pl["items"]
                if item.get("track")
            ]
            playlists.append({"name": pl["name"], "tracks": tracks})
    return playlists


def ensure_schema_columns(con):
    """The zip-upload schema.sql only CREATE TABLE IF NOT EXISTS's, so an
    already-existing playlists table (from before spotify_playlist_id /
    spotify_snapshot_id existed) never picks up the new columns from it.
    Called by the API-based library sync, which is the only caller that
    needs these columns, before it reads/writes them."""
    existing = {row[1] for row in con.execute("PRAGMA table_info(playlists)")}
    if not existing:
        return  # table doesn't exist yet (no upload/export has run) - nothing to migrate
    for col in ("spotify_playlist_id", "spotify_snapshot_id", "image_url", "description"):
        if col not in existing:
            con.execute(f"ALTER TABLE playlists ADD COLUMN {col} TEXT")
    con.commit()


def get_snapshot_ids(con) -> dict:
    """name -> stored spotify_snapshot_id, for the API sync to decide which
    playlists' tracks actually need refetching."""
    return {
        row[0]: row[1]
        for row in con.execute("SELECT name, spotify_snapshot_id FROM playlists")
    }


def save_to_db(con, playlists, prune_missing=True):
    """The uploaded Playlist*.json files are treated as the full, current
    set of the user's playlists. On each import: existing playlists are
    matched by name and have their tracks replaced (so removed/reordered
    tracks are reflected), new playlists are created, and - when
    prune_missing is set - any previously stored playlist absent from this
    import is deleted along with its tracks, so re-uploading overrides
    rather than only ever adding. prune_missing should be False when no
    Playlist*.json files were present at all, so an unrelated upload (e.g.
    history-only) doesn't wipe out existing playlists.

    A playlist dict may optionally carry "spotifyPlaylistId"/"spotifySnapshotId"
    (stored for change detection) and "unchanged": True (set by the API sync
    when the snapshot id matches what's already stored, meaning its track
    list is skipped entirely rather than re-fetched and re-written - the
    dict then omits "tracks"). Zip uploads never set these, so their
    behavior is unchanged."""
    before_playlists = con.execute("SELECT COUNT(*) FROM playlists").fetchone()[0]
    before_tracks = con.execute("SELECT COUNT(*) FROM playlist_tracks").fetchone()[0]

    cur = con.cursor()
    seen_ids = []
    for pl in playlists:
        row = cur.execute("SELECT id FROM playlists WHERE name = ?", (pl["name"],)).fetchone()
        if row:
            playlist_id = row[0]
        else:
            cur.execute("INSERT INTO playlists (name) VALUES (?)", (pl["name"],))
            playlist_id = cur.lastrowid
        seen_ids.append(playlist_id)

        if pl.get("spotifyPlaylistId") is not None:
            cur.execute(
                "UPDATE playlists SET spotify_playlist_id = ?, spotify_snapshot_id = ?, "
                "image_url = COALESCE(?, image_url), description = ? WHERE id = ?",
                (
                    pl["spotifyPlaylistId"],
                    pl.get("spotifySnapshotId"),
                    pl.get("imageUrl"),
                    pl.get("description"),
                    playlist_id,
                ),
            )

        if pl.get("unchanged"):
            continue

        cur.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (playlist_id,))
        cur.executemany(
            "INSERT OR IGNORE INTO playlist_tracks "
            "(playlist_id, track_name, artist_name, spotify_track_uri) VALUES (?, ?, ?, ?)",
            [(playlist_id, t["trackName"], t["artistName"], t["trackUri"]) for t in pl["tracks"]],
        )

    if prune_missing:
        placeholders = ",".join("?" * len(seen_ids))
        stale_ids = [
            row[0]
            for row in cur.execute(
                f"SELECT id FROM playlists WHERE id NOT IN ({placeholders})"
                if seen_ids else "SELECT id FROM playlists",
                seen_ids,
            )
        ]
        for playlist_id in stale_ids:
            cur.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (playlist_id,))
            cur.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))

    con.commit()

    return {
        "new_playlists": con.execute("SELECT COUNT(*) FROM playlists").fetchone()[0]
        - before_playlists,
        "new_playlist_tracks": con.execute("SELECT COUNT(*) FROM playlist_tracks").fetchone()[0]
        - before_tracks,
    }


def main():
    playlists, found_files = process_playlists()
    print(f"Found {len(playlists)} playlists\n")
    for pl in playlists:
        print(f"Playlist: {pl['name']}  ({len(pl['tracks'])} tracks)")
        for t in pl["tracks"]:
            print(f"  - {t['trackName']} — {t['artistName']}")
        print()

    con = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH) as f:
        con.executescript(f.read())
    counts = save_to_db(con, playlists, prune_missing=found_files)
    con.close()

    print(f"Added {counts['new_playlists']} new playlists, "
          f"{counts['new_playlist_tracks']} new playlist tracks, saved to {DB_PATH}")
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
