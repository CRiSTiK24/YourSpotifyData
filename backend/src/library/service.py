import sqlite3


def load_library_tracks(con: sqlite3.Connection) -> list[sqlite3.Row]:
    return con.execute(
        """
        SELECT lt.track_name, lt.artist_name, MAX(th.time) as last_played
        FROM library_tracks lt
        LEFT JOIN track_history th ON th.name = lt.track_name AND th.singer = lt.artist_name
        GROUP BY lt.track_name, lt.artist_name
        ORDER BY last_played DESC NULLS LAST
        """
    ).fetchall()


def load_library_albums(con: sqlite3.Connection) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT album_name, artist_name FROM library_albums ORDER BY artist_name, album_name"
    ).fetchall()
