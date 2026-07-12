import sqlite3

from src.utils import fts_match_query, word_clauses


def search_track_history(con: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    # track_history is 200k+ rows and growing — a LIKE '%word%' scan there is
    # too slow to run on every search. track_history_fts (see schema.sql) is
    # a full-text index over (name, singer), kept in sync via triggers, that
    # turns this into a token lookup instead of a full scan.
    match = fts_match_query(query.split())
    return con.execute(
        """
        SELECT th.name, th.singer, th.time
        FROM track_history_fts
        JOIN track_history th ON th.id = track_history_fts.rowid
        WHERE track_history_fts MATCH ?
        ORDER BY th.time DESC
        """,
        (match,),
    ).fetchall()


def search_library_tracks(con: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    words = query.split()
    where, params = word_clauses(words, "lt.track_name", "lt.artist_name")
    return con.execute(
        f"""
        SELECT lt.track_name, lt.artist_name, ai.image_url
        FROM library_tracks lt
        LEFT JOIN track_history th ON th.name = lt.track_name AND th.singer = lt.artist_name
        LEFT JOIN album_images ai ON ai.artist_name = lt.artist_name AND ai.album_name = th.album
        WHERE {where}
        GROUP BY lt.id
        """,
        params,
    ).fetchall()


def search_library_albums(con: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    words = query.split()
    where, params = word_clauses(words, "a.album_name", "a.artist_name")
    return con.execute(
        f"""
        SELECT a.album_name, a.artist_name, ai.image_url
        FROM library_albums a
        LEFT JOIN album_images ai ON ai.artist_name = a.artist_name AND ai.album_name = a.album_name
        WHERE {where}
        """,
        params,
    ).fetchall()


def search_playlists(con: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    words = query.split()
    where, params = word_clauses(words, "pt.track_name", "pt.artist_name")
    return con.execute(
        f"""
        SELECT pt.track_name, pt.artist_name, p.name AS playlist_name, p.id AS playlist_id,
               ai.image_url
        FROM playlist_tracks pt
        JOIN playlists p ON pt.playlist_id = p.id
        LEFT JOIN track_history th ON th.name = pt.track_name AND th.singer = pt.artist_name
        LEFT JOIN album_images ai ON ai.artist_name = pt.artist_name AND ai.album_name = th.album
        WHERE {where}
        GROUP BY pt.id
        ORDER BY p.name
        """,
        params,
    ).fetchall()
