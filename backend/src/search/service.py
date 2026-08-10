import sqlite3

from src.utils import fts_match_query


def ensure_track_history_fts_covers_album(con: sqlite3.Connection) -> None:
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


def search_track_history_by_name(con: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
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
