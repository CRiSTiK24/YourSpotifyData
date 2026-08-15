import sqlite3


def load_library_albums(con: sqlite3.Connection, user_id: int | None) -> list[sqlite3.Row]:
    user_clause, user_params = ("a.user_id = ?", [user_id]) if user_id is not None else ("1=1", [])
    return con.execute(
        f"""
        SELECT a.album_name, a.artist_name, ai.image_url
        FROM library_albums a
        LEFT JOIN album_images ai ON ai.artist_name = a.artist_name AND ai.album_name = a.album_name
        WHERE {user_clause}
        ORDER BY a.artist_name, a.album_name
        """,
        user_params,
    ).fetchall()
