import sqlite3

from src.utils import word_clauses


def load_artists(con: sqlite3.Connection) -> list[sqlite3.Row]:
    return con.execute(
        """
        SELECT singer, COUNT(*) as play_count
        FROM track_history
        WHERE singer IS NOT NULL AND singer != ''
        GROUP BY singer
        ORDER BY play_count DESC
        """
    ).fetchall()


def search_artists(con: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    words = query.split()
    where, params = word_clauses(words, "singer")
    return con.execute(
        f"SELECT singer, COUNT(*) as play_count FROM track_history "
        f"WHERE singer IS NOT NULL AND singer != '' AND {where} GROUP BY singer ORDER BY play_count DESC",
        params,
    ).fetchall()


def load_artist_history(con: sqlite3.Connection, artist_name: str) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT name, singer, time FROM track_history WHERE singer = ? ORDER BY time DESC",
        (artist_name,),
    ).fetchall()


def load_artist_top_tracks(con: sqlite3.Connection, artist_name: str) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT name, COUNT(*) as cnt FROM track_history WHERE singer = ? GROUP BY name ORDER BY cnt DESC LIMIT 20",
        (artist_name,),
    ).fetchall()
