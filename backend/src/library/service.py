import sqlite3


def load_library_tracks(con: sqlite3.Connection) -> list[sqlite3.Row]:
    return con.execute(
        """
        SELECT lt.track_name, lt.artist_name, MAX(th.time) as last_played, ai.image_url
        FROM library_tracks lt
        LEFT JOIN track_history th ON th.name = lt.track_name AND th.singer = lt.artist_name
        LEFT JOIN album_images ai ON ai.artist_name = lt.artist_name AND ai.album_name = th.album
        GROUP BY lt.track_name, lt.artist_name
        ORDER BY last_played DESC NULLS LAST
        """
    ).fetchall()


def load_library_albums(con: sqlite3.Connection) -> list[sqlite3.Row]:
    return con.execute(
        """
        SELECT a.album_name, a.artist_name, ai.image_url
        FROM library_albums a
        LEFT JOIN album_images ai ON ai.artist_name = a.artist_name AND ai.album_name = a.album_name
        ORDER BY a.artist_name, a.album_name
        """
    ).fetchall()
