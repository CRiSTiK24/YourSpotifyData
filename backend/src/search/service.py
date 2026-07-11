import sqlite3

from src.utils import word_clauses


def search_track_history(con: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    words = query.split()
    where, params = word_clauses(words, "name", "singer")
    return con.execute(
        f"SELECT name, singer, time FROM track_history WHERE {where} ORDER BY time DESC",
        params,
    ).fetchall()


def search_library_tracks(con: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    words = query.split()
    where, params = word_clauses(words, "track_name", "artist_name")
    return con.execute(
        f"SELECT track_name, artist_name FROM library_tracks WHERE {where}",
        params,
    ).fetchall()


def search_library_albums(con: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    words = query.split()
    where, params = word_clauses(words, "album_name", "artist_name")
    return con.execute(
        f"SELECT album_name, artist_name FROM library_albums WHERE {where}",
        params,
    ).fetchall()


def search_playlists(con: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    words = query.split()
    where, params = word_clauses(words, "pt.track_name", "pt.artist_name")
    return con.execute(
        f"""
        SELECT pt.track_name, pt.artist_name, p.name AS playlist_name, p.id AS playlist_id
        FROM playlist_tracks pt
        JOIN playlists p ON pt.playlist_id = p.id
        WHERE {where}
        ORDER BY p.name
        """,
        params,
    ).fetchall()
