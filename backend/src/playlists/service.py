import sqlite3


def load_playlists(con: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT id, name, image_url, description FROM playlists WHERE user_id = ? ORDER BY name",
        (user_id,),
    ).fetchall()


def get_playlist(con: sqlite3.Connection, user_id: int, playlist_id: int) -> sqlite3.Row | None:
    return con.execute(
        "SELECT image_url, description, spotify_playlist_id FROM playlists "
        "WHERE id = ? AND user_id = ?",
        (playlist_id, user_id),
    ).fetchone()


def set_local_description(
    con: sqlite3.Connection, user_id: int, playlist_id: int, description: str
) -> None:
    con.execute(
        "UPDATE playlists SET description = ? WHERE id = ? AND user_id = ?",
        (description, playlist_id, user_id),
    )
    con.commit()


def load_playlist_tracks(
    con: sqlite3.Connection, user_id: int, playlist_id: int
) -> list[sqlite3.Row]:
    return con.execute(
        """
        SELECT pt.track_name, pt.artist_name, ai.image_url,
               (SELECT COUNT(*) FROM track_history th2
                WHERE th2.name = pt.track_name AND th2.singer = pt.artist_name
                  AND th2.user_id = ?) AS play_count
        FROM playlist_tracks pt
        LEFT JOIN track_history th ON th.name = pt.track_name AND th.singer = pt.artist_name
            AND th.user_id = ?
        LEFT JOIN album_images ai ON ai.artist_name = pt.artist_name AND ai.album_name = th.album
        WHERE pt.playlist_id = ? AND pt.user_id = ?
        GROUP BY pt.id
        ORDER BY pt.rowid
        """,
        (user_id, user_id, playlist_id, user_id),
    ).fetchall()


def load_playlist_history_with_album_for_cover_lookup(
    con: sqlite3.Connection, user_id: int, playlist_id: int
) -> list[sqlite3.Row]:
    return con.execute(
        """
        SELECT th.name, th.singer, th.album, th.time
        FROM track_history th
        JOIN playlist_tracks pt ON th.name = pt.track_name AND th.singer = pt.artist_name
        WHERE pt.playlist_id = ? AND pt.user_id = ? AND th.user_id = ?
        ORDER BY th.time DESC
        """,
        (playlist_id, user_id, user_id),
    ).fetchall()


def cover_images_for_artist_album_pairs(
    con: sqlite3.Connection, artist_albums: set[tuple[str, str]]
) -> dict[tuple[str, str], str]:
    if not artist_albums:
        return {}
    placeholders = ",".join("(?,?)" for _ in artist_albums)
    params = [v for pair in artist_albums for v in pair]
    rows = con.execute(
        f"SELECT artist_name, album_name, image_url FROM album_images "
        f"WHERE (artist_name, album_name) IN ({placeholders})",
        params,
    ).fetchall()
    return {(r["artist_name"], r["album_name"]): r["image_url"] for r in rows}
