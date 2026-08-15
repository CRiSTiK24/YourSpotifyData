import sqlite3


def load_track_history(
    con: sqlite3.Connection, user_id: int | None, track_name: str, artist_name: str
) -> list[sqlite3.Row]:
    user_clause, user_params = ("user_id = ?", [user_id]) if user_id is not None else ("1=1", [])
    return con.execute(
        f"SELECT name, singer, album, time, spotify_track_uri FROM track_history "
        f"WHERE {user_clause} AND name = ? AND (singer = ? OR singer IS NULL) ORDER BY time DESC",
        (*user_params, track_name, artist_name),
    ).fetchall()


def load_track_playlists(
    con: sqlite3.Connection, user_id: int | None, track_name: str, artist_name: str
) -> list[sqlite3.Row]:
    if user_id is not None:
        return con.execute(
            """
            SELECT p.id, p.name, NULL AS owner_username FROM playlist_tracks pt
            JOIN playlists p ON pt.playlist_id = p.id
            WHERE pt.user_id = ? AND pt.track_name = ? AND pt.artist_name = ?
            """,
            (user_id, track_name, artist_name),
        ).fetchall()
    return con.execute(
        """
        SELECT p.id, p.name, u.username AS owner_username FROM playlist_tracks pt
        JOIN playlists p ON pt.playlist_id = p.id
        JOIN users u ON u.id = pt.user_id
        WHERE pt.track_name = ? AND pt.artist_name = ?
        """,
        (track_name, artist_name),
    ).fetchall()
