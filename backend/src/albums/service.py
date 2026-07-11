import sqlite3


def load_album_track_history(con: sqlite3.Connection, album_name: str) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT name, singer, time FROM track_history WHERE album = ? ORDER BY time DESC",
        (album_name,),
    ).fetchall()


def get_album_image(con: sqlite3.Connection, artist_name: str, album_name: str) -> str | None:
    row = con.execute(
        "SELECT image_url FROM album_images WHERE artist_name = ? AND album_name = ?",
        (artist_name, album_name),
    ).fetchone()
    return row["image_url"] if row else None
