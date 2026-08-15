import sqlite3

from src.genres import GENRE_ARTIST_SUBQUERY
from src.utils import fts_match_query


def _period_bounds(start_period: int, end_period: int) -> tuple[int, int]:
    return start_period or 190001, end_period or 999912


def _period_clause(start_period: int, end_period: int) -> tuple[str, list]:
    if not start_period and not end_period:
        return "period = 0", []
    lo, hi = _period_bounds(start_period, end_period)
    if lo == hi:
        return "period = ?", [lo]
    return "period BETWEEN ? AND ? AND period != 0", [lo, hi]


def _user_clause(user_id: int | None) -> tuple[str, list]:
    return ("user_id = ?", [user_id]) if user_id is not None else ("1=1", [])


def load_artists(
    con: sqlite3.Connection,
    user_id: int | None,
    limit: int,
    offset: int,
    start_period: int = 0,
    end_period: int = 0,
    genre: str = "",
) -> list[sqlite3.Row]:
    genre_clause = f"AND g.singer IN ({GENRE_ARTIST_SUBQUERY})" if genre else ""
    genre_params = [genre] if genre else []
    user_clause, user_params = _user_clause(user_id)
    period_clause, period_params = _period_clause(start_period, end_period)
    return con.execute(
        f"""
        SELECT g.singer, g.play_count, ai.image_url
        FROM (
            SELECT singer, SUM(play_count) AS play_count
            FROM artist_play_counts
            WHERE {user_clause} AND {period_clause}
            GROUP BY singer
        ) g
        LEFT JOIN artist_images ai ON ai.artist_name = g.singer
        WHERE 1=1 {genre_clause}
        ORDER BY g.play_count DESC
        LIMIT ? OFFSET ?
        """,
        (*user_params, *period_params, *genre_params, limit, offset),
    ).fetchall()


def most_listened_artists_stats(
    con: sqlite3.Connection,
    user_id: int | None,
    start_period: int = 0,
    end_period: int = 0,
    genre: str = "",
) -> tuple[int, int]:
    genre_clause = f"AND singer IN ({GENRE_ARTIST_SUBQUERY})" if genre else ""
    genre_params = [genre] if genre else []
    user_clause, user_params = _user_clause(user_id)
    period_clause, period_params = _period_clause(start_period, end_period)
    row = con.execute(
        f"""
        SELECT COUNT(*), COALESCE(MAX(play_count), 0) FROM (
            SELECT SUM(play_count) AS play_count FROM artist_play_counts
            WHERE {user_clause} AND {period_clause} {genre_clause}
            GROUP BY singer
        )
        """,
        (*user_params, *period_params, *genre_params),
    ).fetchone()
    return row[0], row[1]


def search_artists(con: sqlite3.Connection, user_id: int | None, query: str) -> list[sqlite3.Row]:
    match = fts_match_query(query.split(), column="singer")
    user_clause, user_params = ("th.user_id = ?", [user_id]) if user_id is not None else ("1=1", [])
    return con.execute(
        f"""
        SELECT th.singer, COUNT(*) as play_count, ai.image_url
        FROM track_history_fts
        JOIN track_history th ON th.id = track_history_fts.rowid
        LEFT JOIN artist_images ai ON ai.artist_name = th.singer
        WHERE track_history_fts MATCH ? AND {user_clause}
          AND th.singer IS NOT NULL AND th.singer != ''
        GROUP BY th.singer
        ORDER BY play_count DESC
        """,
        (match, *user_params),
    ).fetchall()


def load_artist_history(
    con: sqlite3.Connection, user_id: int | None, artist_name: str
) -> list[sqlite3.Row]:
    user_clause, user_params = ("user_id = ?", [user_id]) if user_id is not None else ("1=1", [])
    return con.execute(
        f"SELECT name, singer, album, time FROM track_history "
        f"WHERE singer = ? AND {user_clause} ORDER BY time DESC",
        (artist_name, *user_params),
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
    con: sqlite3.Connection, user_id: int | None, artist_name: str, offset: int, limit: int
) -> list[sqlite3.Row]:
    user_clause, user_params = ("th.user_id = ?", [user_id]) if user_id is not None else ("1=1", [])
    return con.execute(
        f"""
        SELECT th.name, COUNT(*) as cnt, ai.image_url
        FROM track_history th
        LEFT JOIN album_images ai ON ai.artist_name = th.singer AND ai.album_name = th.album
        WHERE th.singer = ? AND {user_clause}
        GROUP BY th.name
        ORDER BY cnt DESC, th.name
        LIMIT ? OFFSET ?
        """,
        (artist_name, *user_params, limit + 1, offset),
    ).fetchall()


def get_artist_image(con: sqlite3.Connection, artist_name: str) -> str | None:
    row = con.execute(
        "SELECT image_url FROM artist_images WHERE artist_name = ?", (artist_name,)
    ).fetchone()
    return row["image_url"] if row else None
