import sqlite3


def _year_range_filter(column: str, start_year: int, end_year: int) -> tuple[str, list[str]]:
    """0 on either end means unbounded on that side, so a caller can pin
    just a start or just an end instead of always needing both."""
    clauses = []
    params = []
    if start_year:
        clauses.append(f"strftime('%Y', {column}) >= ?")
        params.append(str(start_year))
    if end_year:
        clauses.append(f"strftime('%Y', {column}) <= ?")
        params.append(str(end_year))
    return ("".join(f" AND {c}" for c in clauses), params)


def load_most_listened(
    con: sqlite3.Connection, limit: int, offset: int, start_year: int = 0, end_year: int = 0
) -> list[sqlite3.Row]:
    """Ranks every distinct track ever played by play count. ai.image_url is
    picked off one arbitrary album per (name, singer) group (same 'good
    enough for a thumbnail' convention as the other GROUP BY + LEFT JOIN
    cover lookups in this codebase, e.g. library/liked_songs above) since a
    track can appear on more than one album in the history."""
    year_filter, year_params = _year_range_filter("th.time", start_year, end_year)
    return con.execute(
        f"""
        SELECT th.name, th.singer, COUNT(*) AS play_count, ai.image_url
        FROM track_history th
        LEFT JOIN album_images ai ON ai.artist_name = th.singer AND ai.album_name = th.album
        WHERE th.name IS NOT NULL AND th.name != ''{year_filter}
        GROUP BY th.name, th.singer
        ORDER BY play_count DESC
        LIMIT ? OFFSET ?
        """,
        (*year_params, limit, offset),
    ).fetchall()


def most_listened_stats(con: sqlite3.Connection, start_year: int = 0, end_year: int = 0) -> tuple[int, int]:
    """(distinct track count, top track's play count) - the latter scales
    every row's bar_fraction against the single most-played track, the
    former goes in the page header."""
    year_filter, year_params = _year_range_filter("time", start_year, end_year)
    row = con.execute(
        f"""
        SELECT COUNT(*), COALESCE(MAX(play_count), 0) FROM (
            SELECT COUNT(*) AS play_count FROM track_history
            WHERE name IS NOT NULL AND name != ''{year_filter} GROUP BY name, singer
        )
        """,
        year_params,
    ).fetchone()
    return row[0], row[1]


def load_most_listened_albums(
    con: sqlite3.Connection, limit: int, offset: int, start_year: int = 0, end_year: int = 0
) -> list[sqlite3.Row]:
    """Same ranking as load_most_listened, grouped by (album, artist)
    instead of (track, artist) - a play of any track on the album counts
    towards it."""
    year_filter, year_params = _year_range_filter("th.time", start_year, end_year)
    return con.execute(
        f"""
        SELECT th.album, th.singer, COUNT(*) AS play_count, ai.image_url
        FROM track_history th
        LEFT JOIN album_images ai ON ai.artist_name = th.singer AND ai.album_name = th.album
        WHERE th.album IS NOT NULL AND th.album != ''
          AND th.singer IS NOT NULL AND th.singer != ''{year_filter}
        GROUP BY th.album, th.singer
        ORDER BY play_count DESC
        LIMIT ? OFFSET ?
        """,
        (*year_params, limit, offset),
    ).fetchall()


def most_listened_albums_stats(
    con: sqlite3.Connection, start_year: int = 0, end_year: int = 0
) -> tuple[int, int]:
    """(distinct album count, top album's play count), same convention as
    most_listened_stats."""
    year_filter, year_params = _year_range_filter("time", start_year, end_year)
    row = con.execute(
        f"""
        SELECT COUNT(*), COALESCE(MAX(play_count), 0) FROM (
            SELECT COUNT(*) AS play_count FROM track_history
            WHERE album IS NOT NULL AND album != ''
              AND singer IS NOT NULL AND singer != ''{year_filter} GROUP BY album, singer
        )
        """,
        year_params,
    ).fetchone()
    return row[0], row[1]


def most_listened_year_range(con: sqlite3.Connection) -> tuple[int, int]:
    """(earliest, latest) play year present in track_history, for sizing the
    year slider. Falls back to the same value twice if history is empty."""
    row = con.execute(
        "SELECT MIN(strftime('%Y', time)), MAX(strftime('%Y', time)) FROM track_history"
    ).fetchone()
    if row[0] is None:
        from datetime import UTC, datetime

        current_year = datetime.now(UTC).year
        return current_year, current_year
    return int(row[0]), int(row[1])


def load_library_albums(con: sqlite3.Connection) -> list[sqlite3.Row]:
    return con.execute(
        """
        SELECT a.album_name, a.artist_name, ai.image_url
        FROM library_albums a
        LEFT JOIN album_images ai ON ai.artist_name = a.artist_name AND ai.album_name = a.album_name
        ORDER BY a.artist_name, a.album_name
        """
    ).fetchall()
