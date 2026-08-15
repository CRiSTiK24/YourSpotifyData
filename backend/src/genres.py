import sqlite3

# Reused everywhere a most-listened query needs to restrict to artists
# tagged with a given genre (artist_images.genres is a JSON array, not a
# normalized table - see load_top_genres_for_period below) - takes exactly
# one "?" bind param (the genre name) and is meant to sit inside an
# "<singer-column> IN (...)" clause.
GENRE_ARTIST_SUBQUERY = (
    "SELECT ai.artist_name FROM artist_images ai, json_each(ai.genres) je WHERE je.value = ?"
)


def load_top_genres_for_period(
    con: sqlite3.Connection,
    user_id: int,
    start_period: int,
    end_period: int,
    limit: int | None = None,
) -> list[sqlite3.Row]:
    # mirrors track_play_counts.period (see library/play_counts.py's
    # ensure_monthly_play_count_tables): CAST(strftime('%Y%m', time) AS
    # INTEGER), computed live here instead of joined from that table since
    # it only tracks play counts, not genre. limit=None omits the LIMIT
    # clause entirely - fine for callers that render every genre in a
    # scrollable/draggable strip rather than a fixed-size widget.
    limit_clause = "LIMIT ?" if limit is not None else ""
    limit_params = [limit] if limit is not None else []
    if not start_period and not end_period:
        return con.execute(
            f"""
            SELECT je.value AS genre, COUNT(*) AS n
            FROM track_history th
            JOIN artist_images ai ON ai.artist_name = th.singer
            JOIN json_each(ai.genres) je
            WHERE th.user_id = ? AND je.value IS NOT NULL AND je.value != ''
            GROUP BY je.value
            ORDER BY n DESC
            {limit_clause}
            """,
            (user_id, *limit_params),
        ).fetchall()
    lo, hi = start_period or 190001, end_period or 999912
    return con.execute(
        f"""
        SELECT je.value AS genre, COUNT(*) AS n
        FROM track_history th
        JOIN artist_images ai ON ai.artist_name = th.singer
        JOIN json_each(ai.genres) je
        WHERE th.user_id = ? AND CAST(strftime('%Y%m', th.time) AS INTEGER) BETWEEN ? AND ?
          AND je.value IS NOT NULL AND je.value != ''
        GROUP BY je.value
        ORDER BY n DESC
        {limit_clause}
        """,
        (user_id, lo, hi, *limit_params),
    ).fetchall()
