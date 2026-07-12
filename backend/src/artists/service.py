import sqlite3

from src.utils import word_clauses


def load_artists(con: sqlite3.Connection) -> list[sqlite3.Row]:
    return con.execute(
        """
        SELECT th.singer, COUNT(*) as play_count, ai.image_url
        FROM track_history th
        LEFT JOIN artist_images ai ON ai.artist_name = th.singer
        WHERE th.singer IS NOT NULL AND th.singer != ''
        GROUP BY th.singer
        ORDER BY play_count DESC
        """
    ).fetchall()


def search_artists(con: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    words = query.split()
    where, params = word_clauses(words, "th.singer")
    return con.execute(
        f"""
        SELECT th.singer, COUNT(*) as play_count, ai.image_url
        FROM track_history th
        LEFT JOIN artist_images ai ON ai.artist_name = th.singer
        WHERE th.singer IS NOT NULL AND th.singer != '' AND {where}
        GROUP BY th.singer
        ORDER BY play_count DESC
        """,
        params,
    ).fetchall()


def load_artist_history(con: sqlite3.Connection, artist_name: str) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT name, singer, time FROM track_history WHERE singer = ? ORDER BY time DESC",
        (artist_name,),
    ).fetchall()


def load_artist_tracks_page(
    con: sqlite3.Connection, artist_name: str, offset: int, limit: int
) -> list[sqlite3.Row]:
    """One page of this artist's tracks, ordered by play count. Fetches
    limit+1 rows so the caller can tell whether there's another page without
    a separate COUNT query."""
    return con.execute(
        """
        SELECT th.name, COUNT(*) as cnt, ai.image_url
        FROM track_history th
        LEFT JOIN album_images ai ON ai.artist_name = th.singer AND ai.album_name = th.album
        WHERE th.singer = ?
        GROUP BY th.name
        ORDER BY cnt DESC, th.name
        LIMIT ? OFFSET ?
        """,
        (artist_name, limit + 1, offset),
    ).fetchall()


def get_artist_image(con: sqlite3.Connection, artist_name: str) -> str | None:
    row = con.execute(
        "SELECT image_url FROM artist_images WHERE artist_name = ?", (artist_name,)
    ).fetchone()
    return row["image_url"] if row else None
