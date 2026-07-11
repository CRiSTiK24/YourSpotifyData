#!/usr/bin/env python3
import json
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
RAW_DIR = os.path.join(BASE_DIR, "data", "spotifyRaw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "spotifyProcessed")
DB_PATH = os.path.join(PROCESSED_DIR, "SpotifyData.db")
SCHEMA_PATH = os.path.join(PROCESSED_DIR, "schema.sql")
LIBRARY_PATH = os.path.join(RAW_DIR, "YourLibrary.json")


def process_library():
    with open(LIBRARY_PATH) as f:
        data = json.load(f)

    tracks = [
        {"track_name": t["track"], "artist_name": t["artist"]}
        for t in data.get("tracks", [])
        if t.get("track") and t.get("artist")
    ]

    albums = [
        {"album_name": a["album"], "artist_name": a["artist"]}
        for a in data.get("albums", [])
        if a.get("album") and a.get("artist")
    ]

    return tracks, albums


def save_to_db(tracks, albums):
    con = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH) as f:
        con.executescript(f.read())

    con.executemany(
        "INSERT INTO library_tracks (track_name, artist_name) VALUES (?, ?)",
        [(t["track_name"], t["artist_name"]) for t in tracks],
    )
    con.executemany(
        "INSERT INTO library_albums (album_name, artist_name) VALUES (?, ?)",
        [(a["album_name"], a["artist_name"]) for a in albums],
    )
    con.commit()
    con.close()


def main():
    tracks, albums = process_library()

    print(f"Found {len(tracks)} library tracks\n")
    for t in tracks[:20]:
        print(f"  {t['track_name']} — {t['artist_name']}")
    if len(tracks) > 20:
        print(f"  ... and {len(tracks) - 20} more")

    print(f"\nFound {len(albums)} library albums\n")
    for a in albums[:20]:
        print(f"  {a['album_name']} — {a['artist_name']}")
    if len(albums) > 20:
        print(f"  ... and {len(albums) - 20} more")

    save_to_db(tracks, albums)
    print(f"\nSaved to {DB_PATH}")


if __name__ == "__main__":
    main()
