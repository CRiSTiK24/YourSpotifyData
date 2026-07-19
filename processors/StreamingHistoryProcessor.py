#!/usr/bin/env python3
import glob
import json
import os
import sqlite3
from collections import Counter
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
RAW_DIR = os.path.join(BASE_DIR, "data", "spotifyRaw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "spotifyProcessed")
DB_PATH = os.path.join(PROCESSED_DIR, "SpotifyData.db")
SCHEMA_PATH = os.path.join(PROCESSED_DIR, "schema.sql")


def _parse_legacy_time(end_time):
    """Legacy exports use 'YYYY-MM-DD HH:MM' with no timezone (assumed UTC)."""
    return datetime.strptime(end_time, "%Y-%m-%d %H:%M").strftime("%Y-%m-%dT%H:%M:%SZ")


def process_streaming_history():
    extended_files = sorted(glob.glob(os.path.join(RAW_DIR, "Streaming_History_Audio*.json")))
    legacy_files = sorted(glob.glob(os.path.join(RAW_DIR, "StreamingHistory_music_*.json")))
    tracks = []
    for path in extended_files:
        with open(path) as f:
            data = json.load(f)
        for entry in data:
            name = entry.get("master_metadata_track_name")
            singer = entry.get("master_metadata_album_artist_name")
            album = entry.get("master_metadata_album_album_name")
            time = entry.get("ts")
            uri = entry.get("spotify_track_uri")
            if name and time:
                tracks.append(
                    {"name": name, "singer": singer, "album": album, "time": time, "uri": uri}
                )
    for path in legacy_files:
        with open(path) as f:
            data = json.load(f)
        for entry in data:
            name = entry.get("trackName")
            singer = entry.get("artistName")
            end_time = entry.get("endTime")
            if name and end_time:
                tracks.append(
                    {
                        "name": name,
                        "singer": singer,
                        "album": None,
                        "time": _parse_legacy_time(end_time),
                        "uri": None,
                    }
                )
    return tracks


def save_to_db(con, tracks):
    """Insert only entries not already stored, so re-running against the
    same (or an overlapping/backfilling) export is a no-op/incremental
    rather than duplicating history. Matches on (name, singer, time) as a
    multiset rather than a plain set, since genuine repeat plays can share
    the same timestamp (especially with legacy exports' minute-only
    granularity) - a plain max-time cutoff would wrongly skip any backfill
    that lands before the newest timestamp already in the DB."""
    existing = Counter(
        con.execute("SELECT name, singer, time FROM track_history").fetchall()
    )
    new_tracks = []
    for t in tracks:
        key = (t["name"], t["singer"], t["time"])
        if existing[key] > 0:
            existing[key] -= 1
        else:
            new_tracks.append(t)

    con.executemany(
        "INSERT INTO track_history (name, singer, album, time, spotify_track_uri) "
        "VALUES (?, ?, ?, ?, ?)",
        [(t["name"], t["singer"], t["album"], t["time"], t["uri"]) for t in new_tracks],
    )
    con.commit()
    return len(new_tracks)


def main():
    tracks = process_streaming_history()
    print(f"Found {len(tracks)} track history entries\n")
    for t in tracks[:20]:
        print(f"  {t['time']}  {t['name']} — {t['singer']}")
    if len(tracks) > 20:
        print(f"  ... and {len(tracks) - 20} more")

    con = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH) as f:
        con.executescript(f.read())
    new_count = save_to_db(con, tracks)
    con.close()

    print(f"\nAdded {new_count} new entries, saved to {DB_PATH}")
    print(json.dumps({"new_history_rows": new_count}))


if __name__ == "__main__":
    main()
