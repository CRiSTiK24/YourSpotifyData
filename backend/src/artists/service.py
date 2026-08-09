import sqlite3

from src.utils import fts_match_query


def _period_bounds(start_period: int, end_period: int) -> tuple[int, int]:
    """0 on either end means unbounded there; widen to an effectively
    unbounded real YYYYMM range so `BETWEEN lo AND hi` still works as a
    plain comparison. Same helper as library/service.py's (small enough,
    and tied closely enough to each module's own *_play_counts table, that
    sharing it across modules wasn't worth the indirection)."""
    return start_period or 190001, end_period or 999912


def load_artists(
    con: sqlite3.Connection, limit: int, offset: int, start_period: int = 0, end_period: int = 0
) -> list[sqlite3.Row]:
    """Ranks every distinct artist by play count - the Artists column/tab
    on the merged /most-listened page. Reads artist_play_counts (see
    library/service.py's ensure_play_count_migrations, which maintains all
    three *_play_counts tables from the same track_history triggers)
    instead of a live GROUP BY over track_history: period=0 is the
    maintained all-time total, a single specific month is also a direct
    row lookup, and only a genuine multi-month range needs to SUM per-month
    rows at read time."""
    if not start_period and not end_period:
        return con.execute(
            """
            SELECT apc.singer, apc.play_count, ai.image_url
            FROM artist_play_counts apc
            LEFT JOIN artist_images ai ON ai.artist_name = apc.singer
            WHERE apc.period = 0
            ORDER BY apc.play_count DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    lo, hi = _period_bounds(start_period, end_period)
    if lo == hi:
        return con.execute(
            """
            SELECT apc.singer, apc.play_count, ai.image_url
            FROM artist_play_counts apc
            LEFT JOIN artist_images ai ON ai.artist_name = apc.singer
            WHERE apc.period = ?
            ORDER BY apc.play_count DESC
            LIMIT ? OFFSET ?
            """,
            (lo, limit, offset),
        ).fetchall()
    return con.execute(
        """
        SELECT g.singer, g.play_count, ai.image_url
        FROM (
            SELECT singer, SUM(play_count) AS play_count
            FROM artist_play_counts
            WHERE period BETWEEN ? AND ? AND period != 0
            GROUP BY singer
        ) g
        LEFT JOIN artist_images ai ON ai.artist_name = g.singer
        ORDER BY g.play_count DESC
        LIMIT ? OFFSET ?
        """,
        (lo, hi, limit, offset),
    ).fetchall()


def most_listened_artists_stats(
    con: sqlite3.Connection, start_period: int = 0, end_period: int = 0
) -> tuple[int, int]:
    """(distinct artist count, top artist's play count), same convention as
    library/service.py's most_listened_stats / most_listened_albums_stats."""
    if not start_period and not end_period:
        row = con.execute(
            "SELECT COUNT(*), COALESCE(MAX(play_count), 0) FROM artist_play_counts WHERE period = 0"
        ).fetchone()
        return row[0], row[1]
    lo, hi = _period_bounds(start_period, end_period)
    if lo == hi:
        row = con.execute(
            "SELECT COUNT(*), COALESCE(MAX(play_count), 0) FROM artist_play_counts WHERE period = ?",
            (lo,),
        ).fetchone()
        return row[0], row[1]
    row = con.execute(
        """
        SELECT COUNT(*), COALESCE(MAX(play_count), 0) FROM (
            SELECT SUM(play_count) AS play_count FROM artist_play_counts
            WHERE period BETWEEN ? AND ? AND period != 0
            GROUP BY singer
        )
        """,
        (lo, hi),
    ).fetchone()
    return row[0], row[1]


def search_artists(con: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    # FTS instead of a LIKE scan, same reasoning as search_track_history -
    # track_history is 200k+ rows and growing. Restricted to the singer
    # column so this only matches on the artist's own name.
    match = fts_match_query(query.split(), column="singer")
    return con.execute(
        """
        SELECT th.singer, COUNT(*) as play_count, ai.image_url
        FROM track_history_fts
        JOIN track_history th ON th.id = track_history_fts.rowid
        LEFT JOIN artist_images ai ON ai.artist_name = th.singer
        WHERE track_history_fts MATCH ? AND th.singer IS NOT NULL AND th.singer != ''
        GROUP BY th.singer
        ORDER BY play_count DESC
        """,
        (match,),
    ).fetchall()


def load_artist_history(con: sqlite3.Connection, artist_name: str) -> list[sqlite3.Row]:
    # album is only here for the heatmap's period-filtered track cards to
    # look up cover art with (see images_for_tracks below) - not used by
    # the heatmap itself.
    return con.execute(
        "SELECT name, singer, album, time FROM track_history WHERE singer = ? ORDER BY time DESC",
        (artist_name,),
    ).fetchall()


def images_for_tracks(con: sqlite3.Connection, artist_name: str, albums: set[str]) -> dict[str, str]:
    """Maps album name -> cover image_url for this artist's albums, for
    looking up cover art on a heatmap-filtered track list (which only has
    each play's own album, not a pre-joined image like
    load_artist_tracks_page's query)."""
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
