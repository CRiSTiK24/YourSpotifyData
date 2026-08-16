import sqlite3

GENRE_ARTIST_SUBQUERY = (
    "SELECT ai.artist_name FROM artist_images ai, json_each(ai.genres) je WHERE je.value = ?"
)


def load_top_genres_for_period(
    con: sqlite3.Connection,
    user_id: int | None,
    start_period: int,
    end_period: int,
    limit: int | None = None,
) -> list[sqlite3.Row]:
    limit_clause = "LIMIT ?" if limit is not None else ""
    limit_params = [limit] if limit is not None else []
    user_clause, user_params = ("th.user_id = ?", [user_id]) if user_id is not None else ("1=1", [])
    if not start_period and not end_period:
        return con.execute(
            f"""
            SELECT je.value AS genre, COUNT(*) AS n
            FROM track_history th
            JOIN artist_images ai ON ai.artist_name = th.singer
            JOIN json_each(ai.genres) je
            WHERE {user_clause} AND je.value IS NOT NULL AND je.value != ''
            GROUP BY je.value
            ORDER BY n DESC
            {limit_clause}
            """,
            (*user_params, *limit_params),
        ).fetchall()
    lo, hi = start_period or 190001, end_period or 999912
    return con.execute(
        f"""
        SELECT je.value AS genre, COUNT(*) AS n
        FROM track_history th
        JOIN artist_images ai ON ai.artist_name = th.singer
        JOIN json_each(ai.genres) je
        WHERE {user_clause} AND CAST(strftime('%Y%m', th.time) AS INTEGER) BETWEEN ? AND ?
          AND je.value IS NOT NULL AND je.value != ''
        GROUP BY je.value
        ORDER BY n DESC
        {limit_clause}
        """,
        (*user_params, lo, hi, *limit_params),
    ).fetchall()
