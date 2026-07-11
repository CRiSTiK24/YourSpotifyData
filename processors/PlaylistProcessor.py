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


def save_to_db(con, playlists):
    """Playlists are matched by name and reused across runs, and tracks are
    inserted with INSERT OR IGNORE against the UNIQUE constraint, so
    re-processing only adds newly-added tracks rather than duplicating the
    playlist or its existing tracks."""
    before_playlists = con.execute("SELECT COUNT(*) FROM playlists").fetchone()[0]
    before_tracks = con.execute("SELECT COUNT(*) FROM playlist_tracks").fetchone()[0]

    cur = con.cursor()
    for pl in playlists:
        row = cur.execute("SELECT id FROM playlists WHERE name = ?", (pl["name"],)).fetchone()
        if row:
            playlist_id = row[0]
        else:
            cur.execute("INSERT INTO playlists (name) VALUES (?)", (pl["name"],))
            playlist_id = cur.lastrowid
        cur.executemany(
            "INSERT OR IGNORE INTO playlist_tracks "
            "(playlist_id, track_name, artist_name, spotify_track_uri) VALUES (?, ?, ?, ?)",
            [(playlist_id, t["trackName"], t["artistName"], t["trackUri"]) for t in pl["tracks"]],
        )
    con.commit()

    return {
        "new_playlists": con.execute("SELECT COUNT(*) FROM playlists").fetchone()[0]
        - before_playlists,
        "new_playlist_tracks": con.execute("SELECT COUNT(*) FROM playlist_tracks").fetchone()[0]
        - before_tracks,
    }


def main():
    playlists = process_playlists()
    print(f"Found {len(playlists)} playlists\n")
    for pl in playlists:
        print(f"Playlist: {pl['name']}  ({len(pl['tracks'])} tracks)")
        for t in pl["tracks"]:
            print(f"  - {t['trackName']} — {t['artistName']}")
        print()

    con = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH) as f:
        con.executescript(f.read())
    counts = save_to_db(con, playlists)
    con.close()

    print(f"Added {counts['new_playlists']} new playlists, "
          f"{counts['new_playlist_tracks']} new playlist tracks, saved to {DB_PATH}")
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
