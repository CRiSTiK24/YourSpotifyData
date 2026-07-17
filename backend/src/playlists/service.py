import sqlite3


def load_playlists(con: sqlite3.Connection) -> list[sqlite3.Row]:
    return con.execute("SELECT id, name, image_url FROM playlists ORDER BY name").fetchall()


def playlist_exists(con: sqlite3.Connection, playlist_id: int) -> bool:
    return con.execute("SELECT 1 FROM playlists WHERE id = ?", (playlist_id,)).fetchone() is not None


def get_playlist(con: sqlite3.Connection, playlist_id: int) -> sqlite3.Row | None:
    return con.execute(
        "SELECT image_url, description FROM playlists WHERE id = ?", (playlist_id,)
    ).fetchone()


def load_playlist_tracks(con: sqlite3.Connection, playlist_id: int) -> list[sqlite3.Row]:
    """play_count is a correlated subquery (not a join+GROUP BY count) since
    a track can join track_history/album_images on multiple rows already -
    counting via a plain COUNT() here would double-count against that join,
    same convention as aggregate_plays() elsewhere in the app."""
    return con.execute(
        """
        SELECT pt.track_name, pt.artist_name, ai.image_url,
               (SELECT COUNT(*) FROM track_history th2
                WHERE th2.name = pt.track_name AND th2.singer = pt.artist_name) AS play_count
        FROM playlist_tracks pt
        LEFT JOIN track_history th ON th.name = pt.track_name AND th.singer = pt.artist_name
        LEFT JOIN album_images ai ON ai.artist_name = pt.artist_name AND ai.album_name = th.album
        WHERE pt.playlist_id = ?
        GROUP BY pt.id
        ORDER BY pt.rowid
        """,
        (playlist_id,),
    ).fetchall()


def load_playlist_history(con: sqlite3.Connection, playlist_id: int) -> list[sqlite3.Row]:
    return con.execute(
        """
        SELECT th.name, th.singer, th.time
        FROM track_history th
        JOIN playlist_tracks pt ON th.name = pt.track_name AND th.singer = pt.artist_name
        WHERE pt.playlist_id = ?
        ORDER BY th.time DESC
        """,
        (playlist_id,),
    ).fetchall()
