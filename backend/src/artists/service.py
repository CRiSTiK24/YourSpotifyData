import sqlite3

from src.genres import GENRE_ARTIST_SUBQUERY
from src.utils import fts_match_query


def _period_bounds(start_period: int, end_period: int) -> tuple[int, int]:
    return start_period or 190001, end_period or 999912


def load_artists(
    con: sqlite3.Connection,
    user_id: int,
    limit: int,
    offset: int,
    start_period: int = 0,
    end_period: int = 0,
    genre: str = "",
) -> list[sqlite3.Row]:
    genre_clause = f"AND apc.singer IN ({GENRE_ARTIST_SUBQUERY})" if genre else ""
    genre_params = [genre] if genre else []
    if not start_period and not end_period:
        return con.execute(
            f"""
            SELECT apc.singer, apc.play_count, ai.image_url
            FROM artist_play_counts apc
            LEFT JOIN artist_images ai ON ai.artist_name = apc.singer
            WHERE apc.user_id = ? AND apc.period = 0 {genre_clause}
            ORDER BY apc.play_count DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, *genre_params, limit, offset),
        ).fetchall()
    lo, hi = _period_bounds(start_period, end_period)
    if lo == hi:
        return con.execute(
            f"""
            SELECT apc.singer, apc.play_count, ai.image_url
            FROM artist_play_counts apc
            LEFT JOIN artist_images ai ON ai.artist_name = apc.singer
            WHERE apc.user_id = ? AND apc.period = ? {genre_clause}
            ORDER BY apc.play_count DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, lo, *genre_params, limit, offset),
        ).fetchall()
    genre_clause_g = f"AND g.singer IN ({GENRE_ARTIST_SUBQUERY})" if genre else ""
    return con.execute(
        f"""
        SELECT g.singer, g.play_count, ai.image_url
        FROM (
            SELECT singer, SUM(play_count) AS play_count
            FROM artist_play_counts
            WHERE user_id = ? AND period BETWEEN ? AND ? AND period != 0
            GROUP BY singer
        ) g
        LEFT JOIN artist_images ai ON ai.artist_name = g.singer
        WHERE 1=1 {genre_clause_g}
        ORDER BY g.play_count DESC
        LIMIT ? OFFSET ?
        """,
        (user_id, lo, hi, *genre_params, limit, offset),
    ).fetchall()


def most_listened_artists_stats(
    con: sqlite3.Connection,
    user_id: int,
    start_period: int = 0,
    end_period: int = 0,
    genre: str = "",
) -> tuple[int, int]:
    genre_clause = f"AND singer IN ({GENRE_ARTIST_SUBQUERY})" if genre else ""
    genre_params = [genre] if genre else []
    if not start_period and not end_period:
        row = con.execute(
            f"SELECT COUNT(*), COALESCE(MAX(play_count), 0) FROM artist_play_counts "
            f"WHERE user_id = ? AND period = 0 {genre_clause}",
            (user_id, *genre_params),
        ).fetchone()
        return row[0], row[1]
    lo, hi = _period_bounds(start_period, end_period)
    if lo == hi:
        row = con.execute(
            f"SELECT COUNT(*), COALESCE(MAX(play_count), 0) FROM artist_play_counts "
            f"WHERE user_id = ? AND period = ? {genre_clause}",
            (user_id, lo, *genre_params),
        ).fetchone()
        return row[0], row[1]
    row = con.execute(
        f"""
        SELECT COUNT(*), COALESCE(MAX(play_count), 0) FROM (
            SELECT SUM(play_count) AS play_count FROM artist_play_counts
            WHERE user_id = ? AND period BETWEEN ? AND ? AND period != 0 {genre_clause}
            GROUP BY singer
        )
        """,
        (user_id, lo, hi, *genre_params),
    ).fetchone()
    return row[0], row[1]


def search_artists(con: sqlite3.Connection, user_id: int, query: str) -> list[sqlite3.Row]:
    match = fts_match_query(query.split(), column="singer")
    return con.execute(
        """
        SELECT th.singer, COUNT(*) as play_count, ai.image_url
        FROM track_history_fts
        JOIN track_history th ON th.id = track_history_fts.rowid
        LEFT JOIN artist_images ai ON ai.artist_name = th.singer
        WHERE track_history_fts MATCH ? AND th.user_id = ?
          AND th.singer IS NOT NULL AND th.singer != ''
        GROUP BY th.singer
        ORDER BY play_count DESC
        """,
        (match, user_id),
    ).fetchall()


def load_artist_history(
    con: sqlite3.Connection, user_id: int, artist_name: str
) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT name, singer, album, time FROM track_history "
        "WHERE singer = ? AND user_id = ? ORDER BY time DESC",
        (artist_name, user_id),
    ).fetchall()


def album_image_urls_by_name(
    con: sqlite3.Connection, artist_name: str, albums: set[str]
) -> dict[str, str]:
    if not albums:
        return {}
    placeholders = ",".join("?" for _ in albums)
    rows = con.execute(
        f"SELECT album_name, image_url FROM album_images "
        f"WHERE artist_name = ? AND album_name IN ({placeholders})",
        (artist_name, *albums),
    ).fetchall()
    return {r["album_name"]: r["image_url"] for r in rows}


def load_artist_tracks_page(
    con: sqlite3.Connection, user_id: int, artist_name: str, offset: int, limit: int
) -> list[sqlite3.Row]:
    return con.execute(
        """
        SELECT th.name, COUNT(*) as cnt, ai.image_url
        FROM track_history th
        LEFT JOIN album_images ai ON ai.artist_name = th.singer AND ai.album_name = th.album
        WHERE th.singer = ? AND th.user_id = ?
        GROUP BY th.name
        ORDER BY cnt DESC, th.name
        LIMIT ? OFFSET ?
        """,
        (artist_name, user_id, limit + 1, offset),
    ).fetchall()


def get_artist_image(con: sqlite3.Connection, artist_name: str) -> str | None:
    row = con.execute(
        "SELECT image_url FROM artist_images WHERE artist_name = ?", (artist_name,)
    ).fetchone()
    return row["image_url"] if row else None
