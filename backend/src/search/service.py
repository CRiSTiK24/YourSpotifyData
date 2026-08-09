import sqlite3

from src.utils import fts_match_query


def ensure_fts_migrations(con: sqlite3.Connection) -> None:
    """track_history_fts originally only indexed (name, singer), so Artists/
    Albums quick-search fell back to LIKE scans against track_history
    directly (200k+ rows - the exact scan the FTS index exists to avoid).
    This rebuilds the FTS table to also cover `album`, one time, so all
    three quick-search tabs get the same fast path. Called unconditionally
    at app startup (see main.py) - cheap no-op once the column is there,
    checked via the stored CREATE statement text rather than a version
    table since that's already the source of truth for what columns exist."""
    row = con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='track_history_fts'"
    ).fetchone()
    if row and "album" in row[0]:
        return
    con.executescript(
        """
        DROP TABLE IF EXISTS track_history_fts;
        CREATE VIRTUAL TABLE track_history_fts USING fts5(
            name, singer, album, content='track_history', content_rowid='id'
        );
        INSERT INTO track_history_fts(track_history_fts) VALUES('rebuild');

        DROP TRIGGER IF EXISTS track_history_ai;
        CREATE TRIGGER track_history_ai AFTER INSERT ON track_history BEGIN
            INSERT INTO track_history_fts(rowid, name, singer, album)
            VALUES (new.id, new.name, new.singer, new.album);
        END;

        DROP TRIGGER IF EXISTS track_history_ad;
        CREATE TRIGGER track_history_ad AFTER DELETE ON track_history BEGIN
            INSERT INTO track_history_fts(track_history_fts, rowid, name, singer, album)
            VALUES ('delete', old.id, old.name, old.singer, old.album);
        END;

        DROP TRIGGER IF EXISTS track_history_au;
        CREATE TRIGGER track_history_au AFTER UPDATE ON track_history BEGIN
            INSERT INTO track_history_fts(track_history_fts, rowid, name, singer, album)
            VALUES ('delete', old.id, old.name, old.singer, old.album);
            INSERT INTO track_history_fts(rowid, name, singer, album)
            VALUES (new.id, new.name, new.singer, new.album);
        END;
        """
    )
    con.commit()


def search_track_history(con: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    # track_history is 200k+ rows and growing — a LIKE '%word%' scan there is
    # too slow to run on every search. track_history_fts (see schema.sql) is
    # a full-text index over (name, singer), kept in sync via triggers, that
    # turns this into a token lookup instead of a full scan. Restricted to
    # the name column - this only feeds the quick-search Tracks tab, which
    # should match on the track's own title, not surface every track by an
    # artist whose name happens to contain the query (that's what the
    # Artists tab is for).
    match = fts_match_query(query.split(), column="name")
    return con.execute(
        """
        SELECT th.name, th.singer, th.time
        FROM track_history_fts
        JOIN track_history th ON th.id = track_history_fts.rowid
        WHERE track_history_fts MATCH ?
        ORDER BY th.time DESC
        """,
        (match,),
    ).fetchall()
