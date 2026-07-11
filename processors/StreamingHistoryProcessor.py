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


def process_streaming_history():
    files = sorted(glob.glob(os.path.join(RAW_DIR, "Streaming_History_Audio*.json")))
    tracks = []
    for path in files:
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
    return tracks


def save_to_db(con, tracks):
    """Insert only entries newer than what's already stored, so re-running
    against the same (or a newer, overlapping) export is a no-op/incremental
    rather than duplicating history."""
    last_max = con.execute("SELECT MAX(time) FROM track_history").fetchone()[0]
    new_tracks = [t for t in tracks if last_max is None or t["time"] > last_max]

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
