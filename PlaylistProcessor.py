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


def process_playlists():
    files = sorted(glob.glob(os.path.join(RAW_DIR, "Playlist*.json")))
    playlists = []
    for path in files:
        with open(path) as f:
            data = json.load(f)
        for pl in data["playlists"]:
            tracks = [
                {
                    "trackName": item["track"]["trackName"],
                    "artistName": item["track"]["artistName"],
                }
                for item in pl["items"]
                if item.get("track")
            ]
            playlists.append({"name": pl["name"], "tracks": tracks})
    return playlists


def save_to_db(playlists):
    con = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH) as f:
        con.executescript(f.read())

    cur = con.cursor()
    for pl in playlists:
        cur.execute("INSERT INTO playlists (name) VALUES (?)", (pl["name"],))
        playlist_id = cur.lastrowid
        cur.executemany(
            "INSERT INTO playlist_tracks (playlist_id, track_name, artist_name) VALUES (?, ?, ?)",
            [(playlist_id, t["trackName"], t["artistName"]) for t in pl["tracks"]],
        )
    con.commit()
    con.close()


def main():
    playlists = process_playlists()
    print(f"Found {len(playlists)} playlists\n")
    for pl in playlists:
        print(f"Playlist: {pl['name']}  ({len(pl['tracks'])} tracks)")
        for t in pl["tracks"]:
            print(f"  - {t['trackName']} — {t['artistName']}")
        print()

    save_to_db(playlists)
    print(f"Saved to {DB_PATH}")


if __name__ == "__main__":
    main()
