#!/usr/bin/env python3
import json
import glob
import os
import sqlite3

BASE_DIR = os.path.dirname(__file__)
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
            time = entry.get("ts")
            if name and time:
                tracks.append({"name": name, "singer": singer, "time": time})
    return tracks


def save_to_db(tracks):
    con = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH) as f:
        con.executescript(f.read())

    con.executemany(
        "INSERT INTO track_history (name, singer, time) VALUES (?, ?, ?)",
        [(t["name"], t["singer"], t["time"]) for t in tracks],
    )
    con.commit()
    con.close()


def main():
    tracks = process_streaming_history()
    print(f"Found {len(tracks)} track history entries\n")
    for t in tracks[:20]:
        print(f"  {t['time']}  {t['name']} — {t['singer']}")
    if len(tracks) > 20:
        print(f"  ... and {len(tracks) - 20} more")

    save_to_db(tracks)
    print(f"\nSaved to {DB_PATH}")


if __name__ == "__main__":
    main()
