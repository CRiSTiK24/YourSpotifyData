import sqlite3


def ensure_play_count_migrations(con: sqlite3.Connection) -> None:
    """Ranking songs/albums/artists by play count (load_most_listened and
    friends below) used to GROUP BY the raw track_history table and ORDER
    BY the aggregate COUNT(*) - no index can shortcut sorting by an
    aggregate, so that's a real full scan+sort every time (measured
    ~500-700ms each on 200k+ rows, and the merged /most-listened page pays
    for songs+albums+artists together). These three tables instead keep a
    running play_count per (entity, period) - period is a YYYYMM integer
    (e.g. 202408), matching the native <input type="month"> filter on
    /most-listened; period=0 is a standing all-time total, kept in
    lockstep so the common "All time" view never has to sum anything -
    maintained incrementally by triggers below rather than recomputed on
    read, so ranking becomes an index range scan on a table with one row
    per (entity, month seen) instead of one row per play.

    Called unconditionally at startup (see main.py). If the tables don't
    exist yet, they're created and backfilled. If they exist but still
    have the older year-granularity schema (a `year` column instead of
    `period` - this table set originally filtered by year, not month),
    they're dropped and rebuilt at month granularity instead of silently
    left stale; otherwise this is a cheap no-op, checked via the stored
    CREATE statement text the same way ensure_fts_migrations checks
    track_history_fts."""
    row = con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='track_play_counts'"
    ).fetchone()
    if row and "period" in row[0]:
        return
    if row:
        con.executescript(
            """
            DROP TABLE IF EXISTS track_play_counts;
            DROP TABLE IF EXISTS album_play_counts;
            DROP TABLE IF EXISTS artist_play_counts;
            DROP TRIGGER IF EXISTS track_play_counts_ai;
            DROP TRIGGER IF EXISTS track_play_counts_ad;
            DROP TRIGGER IF EXISTS track_play_counts_au;
            DROP TRIGGER IF EXISTS album_play_counts_ai;
            DROP TRIGGER IF EXISTS album_play_counts_ad;
            DROP TRIGGER IF EXISTS album_play_counts_au;
            DROP TRIGGER IF EXISTS artist_play_counts_ai;
            DROP TRIGGER IF EXISTS artist_play_counts_ad;
            DROP TRIGGER IF EXISTS artist_play_counts_au;
            """
        )
    con.executescript(
        """
        CREATE TABLE track_play_counts (
            name TEXT NOT NULL,
            singer TEXT NOT NULL DEFAULT '',
            period INTEGER NOT NULL,
            play_count INTEGER NOT NULL,
            album TEXT,
            PRIMARY KEY (name, singer, period)
        );
        CREATE INDEX idx_track_play_counts_period_count ON track_play_counts(period, play_count DESC);

        CREATE TABLE album_play_counts (
            album TEXT NOT NULL,
            singer TEXT NOT NULL,
            period INTEGER NOT NULL,
            play_count INTEGER NOT NULL,
            PRIMARY KEY (album, singer, period)
        );
        CREATE INDEX idx_album_play_counts_period_count ON album_play_counts(period, play_count DESC);

        CREATE TABLE artist_play_counts (
            singer TEXT NOT NULL,
            period INTEGER NOT NULL,
            play_count INTEGER NOT NULL,
            PRIMARY KEY (singer, period)
        );
        CREATE INDEX idx_artist_play_counts_period_count ON artist_play_counts(period, play_count DESC);

        -- One-time backfill from the existing track_history data, both the
        -- per-month rows and the period=0 all-time rows. MAX(album) picks
        -- one arbitrary album per (name, singer) for the all-time/period
        -- rows, same "good enough for a thumbnail" convention already used
        -- elsewhere (e.g. load_most_listened's original album_images join).
        INSERT INTO track_play_counts (name, singer, period, play_count, album)
        SELECT name, COALESCE(singer, ''), CAST(strftime('%Y%m', time) AS INTEGER), COUNT(*), MAX(album)
        FROM track_history WHERE name IS NOT NULL AND name != ''
        GROUP BY name, COALESCE(singer, ''), CAST(strftime('%Y%m', time) AS INTEGER);

        INSERT INTO track_play_counts (name, singer, period, play_count, album)
        SELECT name, COALESCE(singer, ''), 0, COUNT(*), MAX(album)
        FROM track_history WHERE name IS NOT NULL AND name != ''
        GROUP BY name, COALESCE(singer, '');

        INSERT INTO album_play_counts (album, singer, period, play_count)
        SELECT album, singer, CAST(strftime('%Y%m', time) AS INTEGER), COUNT(*)
        FROM track_history WHERE album IS NOT NULL AND album != '' AND singer IS NOT NULL AND singer != ''
        GROUP BY album, singer, CAST(strftime('%Y%m', time) AS INTEGER);

        INSERT INTO album_play_counts (album, singer, period, play_count)
        SELECT album, singer, 0, COUNT(*)
        FROM track_history WHERE album IS NOT NULL AND album != '' AND singer IS NOT NULL AND singer != ''
        GROUP BY album, singer;

        INSERT INTO artist_play_counts (singer, period, play_count)
        SELECT singer, CAST(strftime('%Y%m', time) AS INTEGER), COUNT(*)
        FROM track_history WHERE singer IS NOT NULL AND singer != ''
        GROUP BY singer, CAST(strftime('%Y%m', time) AS INTEGER);

        INSERT INTO artist_play_counts (singer, period, play_count)
        SELECT singer, 0, COUNT(*)
        FROM track_history WHERE singer IS NOT NULL AND singer != ''
        GROUP BY singer;

        -- Kept incrementally in sync from here on. track_history is
        -- insert-only in every code path today (uploads, scrobbler sync),
        -- but the AD/AU triggers exist anyway for the same reason
        -- track_history_fts's do - so a future delete/edit path (or a
        -- one-off manual fix) can't silently drift these tables out of
        -- sync with reality.
        CREATE TRIGGER track_play_counts_ai AFTER INSERT ON track_history
        WHEN new.name IS NOT NULL AND new.name != ''
        BEGIN
            INSERT INTO track_play_counts (name, singer, period, play_count, album)
            VALUES (new.name, COALESCE(new.singer, ''), CAST(strftime('%Y%m', new.time) AS INTEGER), 1, new.album)
            ON CONFLICT (name, singer, period) DO UPDATE SET play_count = play_count + 1, album = excluded.album;
            INSERT INTO track_play_counts (name, singer, period, play_count, album)
            VALUES (new.name, COALESCE(new.singer, ''), 0, 1, new.album)
            ON CONFLICT (name, singer, period) DO UPDATE SET play_count = play_count + 1, album = excluded.album;
        END;

        CREATE TRIGGER track_play_counts_ad AFTER DELETE ON track_history
        WHEN old.name IS NOT NULL AND old.name != ''
        BEGIN
            UPDATE track_play_counts SET play_count = play_count - 1
                WHERE name = old.name AND singer = COALESCE(old.singer, '')
                  AND period = CAST(strftime('%Y%m', old.time) AS INTEGER);
            DELETE FROM track_play_counts
                WHERE name = old.name AND singer = COALESCE(old.singer, '')
                  AND period = CAST(strftime('%Y%m', old.time) AS INTEGER) AND play_count <= 0;
            UPDATE track_play_counts SET play_count = play_count - 1
                WHERE name = old.name AND singer = COALESCE(old.singer, '') AND period = 0;
            DELETE FROM track_play_counts
                WHERE name = old.name AND singer = COALESCE(old.singer, '') AND period = 0 AND play_count <= 0;
        END;

        CREATE TRIGGER album_play_counts_ai AFTER INSERT ON track_history
        WHEN new.album IS NOT NULL AND new.album != '' AND new.singer IS NOT NULL AND new.singer != ''
        BEGIN
            INSERT INTO album_play_counts (album, singer, period, play_count)
            VALUES (new.album, new.singer, CAST(strftime('%Y%m', new.time) AS INTEGER), 1)
            ON CONFLICT (album, singer, period) DO UPDATE SET play_count = play_count + 1;
            INSERT INTO album_play_counts (album, singer, period, play_count)
            VALUES (new.album, new.singer, 0, 1)
            ON CONFLICT (album, singer, period) DO UPDATE SET play_count = play_count + 1;
        END;

        CREATE TRIGGER album_play_counts_ad AFTER DELETE ON track_history
        WHEN old.album IS NOT NULL AND old.album != '' AND old.singer IS NOT NULL AND old.singer != ''
        BEGIN
            UPDATE album_play_counts SET play_count = play_count - 1
                WHERE album = old.album AND singer = old.singer
                  AND period = CAST(strftime('%Y%m', old.time) AS INTEGER);
            DELETE FROM album_play_counts
                WHERE album = old.album AND singer = old.singer
                  AND period = CAST(strftime('%Y%m', old.time) AS INTEGER) AND play_count <= 0;
            UPDATE album_play_counts SET play_count = play_count - 1
                WHERE album = old.album AND singer = old.singer AND period = 0;
            DELETE FROM album_play_counts
                WHERE album = old.album AND singer = old.singer AND period = 0 AND play_count <= 0;
        END;

        CREATE TRIGGER artist_play_counts_ai AFTER INSERT ON track_history
        WHEN new.singer IS NOT NULL AND new.singer != ''
        BEGIN
            INSERT INTO artist_play_counts (singer, period, play_count)
            VALUES (new.singer, CAST(strftime('%Y%m', new.time) AS INTEGER), 1)
            ON CONFLICT (singer, period) DO UPDATE SET play_count = play_count + 1;
            INSERT INTO artist_play_counts (singer, period, play_count)
            VALUES (new.singer, 0, 1)
            ON CONFLICT (singer, period) DO UPDATE SET play_count = play_count + 1;
        END;

        CREATE TRIGGER artist_play_counts_ad AFTER DELETE ON track_history
        WHEN old.singer IS NOT NULL AND old.singer != ''
        BEGIN
            UPDATE artist_play_counts SET play_count = play_count - 1
                WHERE singer = old.singer AND period = CAST(strftime('%Y%m', old.time) AS INTEGER);
            DELETE FROM artist_play_counts
                WHERE singer = old.singer AND period = CAST(strftime('%Y%m', old.time) AS INTEGER) AND play_count <= 0;
            UPDATE artist_play_counts SET play_count = play_count - 1
                WHERE singer = old.singer AND period = 0;
            DELETE FROM artist_play_counts
                WHERE singer = old.singer AND period = 0 AND play_count <= 0;
        END;

        -- AU = the AD logic for the old row's counts, then the AI logic
        -- for the new row's counts, combined in one trigger body per
        -- table (same "delete old, insert new" shape as
        -- track_history_fts's own AU trigger).
        CREATE TRIGGER track_play_counts_au AFTER UPDATE ON track_history
        BEGIN
            UPDATE track_play_counts SET play_count = play_count - 1
                WHERE old.name IS NOT NULL AND old.name != ''
                  AND name = old.name AND singer = COALESCE(old.singer, '')
                  AND period = CAST(strftime('%Y%m', old.time) AS INTEGER);
            DELETE FROM track_play_counts
                WHERE old.name IS NOT NULL AND old.name != ''
                  AND name = old.name AND singer = COALESCE(old.singer, '')
                  AND period = CAST(strftime('%Y%m', old.time) AS INTEGER) AND play_count <= 0;
            UPDATE track_play_counts SET play_count = play_count - 1
                WHERE old.name IS NOT NULL AND old.name != ''
                  AND name = old.name AND singer = COALESCE(old.singer, '') AND period = 0;
            DELETE FROM track_play_counts
                WHERE old.name IS NOT NULL AND old.name != ''
                  AND name = old.name AND singer = COALESCE(old.singer, '') AND period = 0 AND play_count <= 0;

            INSERT INTO track_play_counts (name, singer, period, play_count, album)
            SELECT new.name, COALESCE(new.singer, ''), CAST(strftime('%Y%m', new.time) AS INTEGER), 1, new.album
            WHERE new.name IS NOT NULL AND new.name != ''
            ON CONFLICT (name, singer, period) DO UPDATE SET play_count = play_count + 1, album = excluded.album;
            INSERT INTO track_play_counts (name, singer, period, play_count, album)
            SELECT new.name, COALESCE(new.singer, ''), 0, 1, new.album
            WHERE new.name IS NOT NULL AND new.name != ''
            ON CONFLICT (name, singer, period) DO UPDATE SET play_count = play_count + 1, album = excluded.album;
        END;

        CREATE TRIGGER album_play_counts_au AFTER UPDATE ON track_history
        BEGIN
            UPDATE album_play_counts SET play_count = play_count - 1
                WHERE old.album IS NOT NULL AND old.album != '' AND old.singer IS NOT NULL AND old.singer != ''
                  AND album = old.album AND singer = old.singer
                  AND period = CAST(strftime('%Y%m', old.time) AS INTEGER);
            DELETE FROM album_play_counts
                WHERE old.album IS NOT NULL AND old.album != '' AND old.singer IS NOT NULL AND old.singer != ''
                  AND album = old.album AND singer = old.singer
                  AND period = CAST(strftime('%Y%m', old.time) AS INTEGER) AND play_count <= 0;
            UPDATE album_play_counts SET play_count = play_count - 1
                WHERE old.album IS NOT NULL AND old.album != '' AND old.singer IS NOT NULL AND old.singer != ''
                  AND album = old.album AND singer = old.singer AND period = 0;
            DELETE FROM album_play_counts
                WHERE old.album IS NOT NULL AND old.album != '' AND old.singer IS NOT NULL AND old.singer != ''
                  AND album = old.album AND singer = old.singer AND period = 0 AND play_count <= 0;

            INSERT INTO album_play_counts (album, singer, period, play_count)
            SELECT new.album, new.singer, CAST(strftime('%Y%m', new.time) AS INTEGER), 1
            WHERE new.album IS NOT NULL AND new.album != '' AND new.singer IS NOT NULL AND new.singer != ''
            ON CONFLICT (album, singer, period) DO UPDATE SET play_count = play_count + 1;
            INSERT INTO album_play_counts (album, singer, period, play_count)
            SELECT new.album, new.singer, 0, 1
            WHERE new.album IS NOT NULL AND new.album != '' AND new.singer IS NOT NULL AND new.singer != ''
            ON CONFLICT (album, singer, period) DO UPDATE SET play_count = play_count + 1;
        END;

        CREATE TRIGGER artist_play_counts_au AFTER UPDATE ON track_history
        BEGIN
            UPDATE artist_play_counts SET play_count = play_count - 1
                WHERE old.singer IS NOT NULL AND old.singer != ''
                  AND singer = old.singer AND period = CAST(strftime('%Y%m', old.time) AS INTEGER);
            DELETE FROM artist_play_counts
                WHERE old.singer IS NOT NULL AND old.singer != ''
                  AND singer = old.singer AND period = CAST(strftime('%Y%m', old.time) AS INTEGER) AND play_count <= 0;
            UPDATE artist_play_counts SET play_count = play_count - 1
                WHERE old.singer IS NOT NULL AND old.singer != '' AND singer = old.singer AND period = 0;
            DELETE FROM artist_play_counts
                WHERE old.singer IS NOT NULL AND old.singer != '' AND singer = old.singer AND period = 0 AND play_count <= 0;

            INSERT INTO artist_play_counts (singer, period, play_count)
            SELECT new.singer, CAST(strftime('%Y%m', new.time) AS INTEGER), 1
            WHERE new.singer IS NOT NULL AND new.singer != ''
            ON CONFLICT (singer, period) DO UPDATE SET play_count = play_count + 1;
            INSERT INTO artist_play_counts (singer, period, play_count)
            SELECT new.singer, 0, 1
            WHERE new.singer IS NOT NULL AND new.singer != ''
            ON CONFLICT (singer, period) DO UPDATE SET play_count = play_count + 1;
        END;
        """
    )
    con.commit()


def _period_bounds(start_period: int, end_period: int) -> tuple[int, int]:
    """0 on either end means unbounded there; widen to an effectively
    unbounded real YYYYMM range so `BETWEEN lo AND hi` still works as a
    plain comparison."""
    return start_period or 190001, end_period or 999912


def load_most_listened(
    con: sqlite3.Connection, limit: int, offset: int, start_period: int = 0, end_period: int = 0
) -> list[sqlite3.Row]:
    """Ranks every distinct track ever played by play count, via
    track_play_counts (see ensure_play_count_migrations) instead of a live
    GROUP BY over track_history - period=0 is the maintained all-time
    total (no summing needed for the common "All time" view), a single
    specific month is also a direct row lookup, and only a genuine
    multi-month range needs to SUM per-month rows at read time. ai.image_url
    is picked off one arbitrary album per (name, singer) (same 'good
    enough for a thumbnail' convention as the other GROUP BY + LEFT JOIN
    cover lookups in this codebase) since a track can appear on more than
    one album."""
    if not start_period and not end_period:
        return con.execute(
            """
            SELECT tpc.name, tpc.singer, tpc.play_count, ai.image_url
            FROM track_play_counts tpc
            LEFT JOIN album_images ai ON ai.artist_name = tpc.singer AND ai.album_name = tpc.album
            WHERE tpc.period = 0
            ORDER BY tpc.play_count DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    lo, hi = _period_bounds(start_period, end_period)
    if lo == hi:
        return con.execute(
            """
            SELECT tpc.name, tpc.singer, tpc.play_count, ai.image_url
            FROM track_play_counts tpc
            LEFT JOIN album_images ai ON ai.artist_name = tpc.singer AND ai.album_name = tpc.album
            WHERE tpc.period = ?
            ORDER BY tpc.play_count DESC
            LIMIT ? OFFSET ?
            """,
            (lo, limit, offset),
        ).fetchall()
    return con.execute(
        """
        SELECT g.name, g.singer, g.play_count, ai.image_url
        FROM (
            SELECT name, singer, SUM(play_count) AS play_count, MAX(album) AS album
            FROM track_play_counts
            WHERE period BETWEEN ? AND ? AND period != 0
            GROUP BY name, singer
        ) g
        LEFT JOIN album_images ai ON ai.artist_name = g.singer AND ai.album_name = g.album
        ORDER BY g.play_count DESC
        LIMIT ? OFFSET ?
        """,
        (lo, hi, limit, offset),
    ).fetchall()


def most_listened_stats(
    con: sqlite3.Connection, start_period: int = 0, end_period: int = 0
) -> tuple[int, int]:
    """(distinct track count, top track's play count) - the latter scales
    every row's bar_fraction against the single most-played track, the
    former goes in the page header."""
    if not start_period and not end_period:
        row = con.execute(
            "SELECT COUNT(*), COALESCE(MAX(play_count), 0) FROM track_play_counts WHERE period = 0"
        ).fetchone()
        return row[0], row[1]
    lo, hi = _period_bounds(start_period, end_period)
    if lo == hi:
        row = con.execute(
            "SELECT COUNT(*), COALESCE(MAX(play_count), 0) FROM track_play_counts WHERE period = ?",
            (lo,),
        ).fetchone()
        return row[0], row[1]
    row = con.execute(
        """
        SELECT COUNT(*), COALESCE(MAX(play_count), 0) FROM (
            SELECT SUM(play_count) AS play_count FROM track_play_counts
            WHERE period BETWEEN ? AND ? AND period != 0
            GROUP BY name, singer
        )
        """,
        (lo, hi),
    ).fetchone()
    return row[0], row[1]


def load_most_listened_albums(
    con: sqlite3.Connection, limit: int, offset: int, start_period: int = 0, end_period: int = 0
) -> list[sqlite3.Row]:
    """Same ranking as load_most_listened, via album_play_counts - grouped
    by (album, artist) instead of (track, artist), a play of any track on
    the album counts towards it."""
    if not start_period and not end_period:
        return con.execute(
            """
            SELECT apc.album, apc.singer, apc.play_count, ai.image_url
            FROM album_play_counts apc
            LEFT JOIN album_images ai ON ai.artist_name = apc.singer AND ai.album_name = apc.album
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
            SELECT apc.album, apc.singer, apc.play_count, ai.image_url
            FROM album_play_counts apc
            LEFT JOIN album_images ai ON ai.artist_name = apc.singer AND ai.album_name = apc.album
            WHERE apc.period = ?
            ORDER BY apc.play_count DESC
            LIMIT ? OFFSET ?
            """,
            (lo, limit, offset),
        ).fetchall()
    return con.execute(
        """
        SELECT g.album, g.singer, g.play_count, ai.image_url
        FROM (
            SELECT album, singer, SUM(play_count) AS play_count
            FROM album_play_counts
            WHERE period BETWEEN ? AND ? AND period != 0
            GROUP BY album, singer
        ) g
        LEFT JOIN album_images ai ON ai.artist_name = g.singer AND ai.album_name = g.album
        ORDER BY g.play_count DESC
        LIMIT ? OFFSET ?
        """,
        (lo, hi, limit, offset),
    ).fetchall()


def most_listened_albums_stats(
    con: sqlite3.Connection, start_period: int = 0, end_period: int = 0
) -> tuple[int, int]:
    """(distinct album count, top album's play count), same convention as
    most_listened_stats."""
    if not start_period and not end_period:
        row = con.execute(
            "SELECT COUNT(*), COALESCE(MAX(play_count), 0) FROM album_play_counts WHERE period = 0"
        ).fetchone()
        return row[0], row[1]
    lo, hi = _period_bounds(start_period, end_period)
    if lo == hi:
        row = con.execute(
            "SELECT COUNT(*), COALESCE(MAX(play_count), 0) FROM album_play_counts WHERE period = ?",
            (lo,),
        ).fetchone()
        return row[0], row[1]
    row = con.execute(
        """
        SELECT COUNT(*), COALESCE(MAX(play_count), 0) FROM (
            SELECT SUM(play_count) AS play_count FROM album_play_counts
            WHERE period BETWEEN ? AND ? AND period != 0
            GROUP BY album, singer
        )
        """,
        (lo, hi),
    ).fetchone()
    return row[0], row[1]


def most_listened_period_range(con: sqlite3.Connection) -> tuple[int, int]:
    """(earliest, latest) YYYYMM play period present, for sizing the
    <input type="month"> filter's min/max - reads track_play_counts
    (small, integer period column) rather than parsing every
    track_history timestamp with strftime. Falls back to the current
    month twice if history is empty."""
    row = con.execute(
        "SELECT MIN(period), MAX(period) FROM track_play_counts WHERE period != 0"
    ).fetchone()
    if row[0] is None:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        current_period = now.year * 100 + now.month
        return current_period, current_period
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
