import sqlite3

from src.genres import GENRE_ARTIST_SUBQUERY


def ensure_monthly_play_count_tables(con: sqlite3.Connection) -> None:
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


def _widen_unbounded_period_range(start_period: int, end_period: int) -> tuple[int, int]:
    return start_period or 190001, end_period or 999912


def load_most_listened(
    con: sqlite3.Connection,
    limit: int,
    offset: int,
    start_period: int = 0,
    end_period: int = 0,
    genre: str = "",
) -> list[sqlite3.Row]:
    genre_clause = f"AND tpc.singer IN ({GENRE_ARTIST_SUBQUERY})" if genre else ""
    genre_params = [genre] if genre else []
    if not start_period and not end_period:
        return con.execute(
            f"""
            SELECT tpc.name, tpc.singer, tpc.play_count, ai.image_url
            FROM track_play_counts tpc
            LEFT JOIN album_images ai ON ai.artist_name = tpc.singer AND ai.album_name = tpc.album
            WHERE tpc.period = 0 {genre_clause}
            ORDER BY tpc.play_count DESC
            LIMIT ? OFFSET ?
            """,
            (*genre_params, limit, offset),
        ).fetchall()
    lo, hi = _widen_unbounded_period_range(start_period, end_period)
    if lo == hi:
        return con.execute(
            f"""
            SELECT tpc.name, tpc.singer, tpc.play_count, ai.image_url
            FROM track_play_counts tpc
            LEFT JOIN album_images ai ON ai.artist_name = tpc.singer AND ai.album_name = tpc.album
            WHERE tpc.period = ? {genre_clause}
            ORDER BY tpc.play_count DESC
            LIMIT ? OFFSET ?
            """,
            (lo, *genre_params, limit, offset),
        ).fetchall()
    genre_clause_g = f"AND g.singer IN ({GENRE_ARTIST_SUBQUERY})" if genre else ""
    return con.execute(
        f"""
        SELECT g.name, g.singer, g.play_count, ai.image_url
        FROM (
            SELECT name, singer, SUM(play_count) AS play_count, MAX(album) AS album
            FROM track_play_counts
            WHERE period BETWEEN ? AND ? AND period != 0
            GROUP BY name, singer
        ) g
        LEFT JOIN album_images ai ON ai.artist_name = g.singer AND ai.album_name = g.album
        WHERE 1=1 {genre_clause_g}
        ORDER BY g.play_count DESC
        LIMIT ? OFFSET ?
        """,
        (lo, hi, *genre_params, limit, offset),
    ).fetchall()


def most_listened_stats(
    con: sqlite3.Connection, start_period: int = 0, end_period: int = 0, genre: str = ""
) -> tuple[int, int]:
    genre_clause = f"AND singer IN ({GENRE_ARTIST_SUBQUERY})" if genre else ""
    genre_params = [genre] if genre else []
    if not start_period and not end_period:
        row = con.execute(
            f"SELECT COUNT(*), COALESCE(MAX(play_count), 0) FROM track_play_counts "
            f"WHERE period = 0 {genre_clause}",
            genre_params,
        ).fetchone()
        return row[0], row[1]
    lo, hi = _widen_unbounded_period_range(start_period, end_period)
    if lo == hi:
        row = con.execute(
            f"SELECT COUNT(*), COALESCE(MAX(play_count), 0) FROM track_play_counts "
            f"WHERE period = ? {genre_clause}",
            (lo, *genre_params),
        ).fetchone()
        return row[0], row[1]
    row = con.execute(
        f"""
        SELECT COUNT(*), COALESCE(MAX(play_count), 0) FROM (
            SELECT SUM(play_count) AS play_count FROM track_play_counts
            WHERE period BETWEEN ? AND ? AND period != 0 {genre_clause}
            GROUP BY name, singer
        )
        """,
        (lo, hi, *genre_params),
    ).fetchone()
    return row[0], row[1]


def load_most_listened_albums(
    con: sqlite3.Connection,
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
            SELECT apc.album, apc.singer, apc.play_count, ai.image_url
            FROM album_play_counts apc
            LEFT JOIN album_images ai ON ai.artist_name = apc.singer AND ai.album_name = apc.album
            WHERE apc.period = 0 {genre_clause}
            ORDER BY apc.play_count DESC
            LIMIT ? OFFSET ?
            """,
            (*genre_params, limit, offset),
        ).fetchall()
    lo, hi = _widen_unbounded_period_range(start_period, end_period)
    if lo == hi:
        return con.execute(
            f"""
            SELECT apc.album, apc.singer, apc.play_count, ai.image_url
            FROM album_play_counts apc
            LEFT JOIN album_images ai ON ai.artist_name = apc.singer AND ai.album_name = apc.album
            WHERE apc.period = ? {genre_clause}
            ORDER BY apc.play_count DESC
            LIMIT ? OFFSET ?
            """,
            (lo, *genre_params, limit, offset),
        ).fetchall()
    genre_clause_g = f"AND g.singer IN ({GENRE_ARTIST_SUBQUERY})" if genre else ""
    return con.execute(
        f"""
        SELECT g.album, g.singer, g.play_count, ai.image_url
        FROM (
            SELECT album, singer, SUM(play_count) AS play_count
            FROM album_play_counts
            WHERE period BETWEEN ? AND ? AND period != 0
            GROUP BY album, singer
        ) g
        LEFT JOIN album_images ai ON ai.artist_name = g.singer AND ai.album_name = g.album
        WHERE 1=1 {genre_clause_g}
        ORDER BY g.play_count DESC
        LIMIT ? OFFSET ?
        """,
        (lo, hi, *genre_params, limit, offset),
    ).fetchall()


def most_listened_albums_stats(
    con: sqlite3.Connection, start_period: int = 0, end_period: int = 0, genre: str = ""
) -> tuple[int, int]:
    genre_clause = f"AND singer IN ({GENRE_ARTIST_SUBQUERY})" if genre else ""
    genre_params = [genre] if genre else []
    if not start_period and not end_period:
        row = con.execute(
            f"SELECT COUNT(*), COALESCE(MAX(play_count), 0) FROM album_play_counts "
            f"WHERE period = 0 {genre_clause}",
            genre_params,
        ).fetchone()
        return row[0], row[1]
    lo, hi = _widen_unbounded_period_range(start_period, end_period)
    if lo == hi:
        row = con.execute(
            f"SELECT COUNT(*), COALESCE(MAX(play_count), 0) FROM album_play_counts "
            f"WHERE period = ? {genre_clause}",
            (lo, *genre_params),
        ).fetchone()
        return row[0], row[1]
    row = con.execute(
        f"""
        SELECT COUNT(*), COALESCE(MAX(play_count), 0) FROM (
            SELECT SUM(play_count) AS play_count FROM album_play_counts
            WHERE period BETWEEN ? AND ? AND period != 0 {genre_clause}
            GROUP BY album, singer
        )
        """,
        (lo, hi, *genre_params),
    ).fetchone()
    return row[0], row[1]


def most_listened_period_range(con: sqlite3.Connection) -> tuple[int, int]:
    row = con.execute(
        "SELECT MIN(period), MAX(period) FROM track_play_counts WHERE period != 0"
    ).fetchone()
    if row[0] is None:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        current_period = now.year * 100 + now.month
        return current_period, current_period
    return int(row[0]), int(row[1])
