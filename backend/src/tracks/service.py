import sqlite3


def load_track_history(
    con: sqlite3.Connection, track_name: str, artist_name: str
) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT name, singer, album, time FROM track_history "
        "WHERE name = ? AND (singer = ? OR singer IS NULL) ORDER BY time DESC",
        (track_name, artist_name),
    ).fetchall()


def load_track_playlists(
    con: sqlite3.Connection, track_name: str, artist_name: str
) -> list[sqlite3.Row]:
    return con.execute(
        """
        SELECT p.id, p.name FROM playlist_tracks pt
        JOIN playlists p ON pt.playlist_id = p.id
        WHERE pt.track_name = ? AND pt.artist_name = ?
        """,
        (track_name, artist_name),
    ).fetchall()
