import sqlite3


def load_album_track_history(con: sqlite3.Connection, album_name: str) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT name, singer, time FROM track_history WHERE album = ? ORDER BY time DESC",
        (album_name,),
    ).fetchall()
