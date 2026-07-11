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
        {"track_name": t["track"], "artist_name": t["artist"], "uri": t.get("uri")}
        for t in data.get("tracks", [])
        if t.get("track") and t.get("artist")
    ]

    albums = [
        {"album_name": a["album"], "artist_name": a["artist"], "uri": a.get("uri")}
        for a in data.get("albums", [])
        if a.get("album") and a.get("artist")
    ]

    artists = [
        {"artist_name": a["name"], "uri": a.get("uri")}
        for a in data.get("artists", [])
        if a.get("name")
    ]

    return tracks, albums, artists


def _count(con, table):
    return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def save_to_db(con, tracks, albums, artists):
    """YourLibrary.json always reflects the full current state, so re-running
    against it should only add genuinely new liked items (INSERT OR IGNORE
    against the UNIQUE constraints) rather than duplicating unchanged ones."""
    before_tracks = _count(con, "library_tracks")
    before_albums = _count(con, "library_albums")
    before_artists = _count(con, "library_artists")

    con.executemany(
        "INSERT OR IGNORE INTO library_tracks (track_name, artist_name, spotify_track_uri) "
        "VALUES (?, ?, ?)",
        [(t["track_name"], t["artist_name"], t["uri"]) for t in tracks],
    )
    con.executemany(
        "INSERT OR IGNORE INTO library_albums (album_name, artist_name, spotify_album_uri) "
        "VALUES (?, ?, ?)",
        [(a["album_name"], a["artist_name"], a["uri"]) for a in albums],
    )
    con.executemany(
        "INSERT OR IGNORE INTO library_artists (artist_name, spotify_artist_uri) VALUES (?, ?)",
        [(a["artist_name"], a["uri"]) for a in artists],
    )
    con.commit()

    return {
        "new_library_tracks": _count(con, "library_tracks") - before_tracks,
        "new_library_albums": _count(con, "library_albums") - before_albums,
        "new_library_artists": _count(con, "library_artists") - before_artists,
    }


def main():
    tracks, albums, artists = process_library()

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

    print(f"\nFound {len(artists)} library artists\n")
    for a in artists[:20]:
        print(f"  {a['artist_name']}")
    if len(artists) > 20:
        print(f"  ... and {len(artists) - 20} more")

    con = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH) as f:
        con.executescript(f.read())
    counts = save_to_db(con, tracks, albums, artists)
    con.close()

    print(f"\nAdded {counts['new_library_tracks']} new tracks, "
          f"{counts['new_library_albums']} new albums, "
          f"{counts['new_library_artists']} new artists, saved to {DB_PATH}")
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
