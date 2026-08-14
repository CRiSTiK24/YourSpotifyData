import sqlite3

from src.utils import fts_match_query


def search_albums(con: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    match = fts_match_query(query.split(), column="album")
    return con.execute(
        """
        SELECT th.album, th.singer, COUNT(*) AS play_count, ai.image_url
        FROM track_history_fts
        JOIN track_history th ON th.id = track_history_fts.rowid
        LEFT JOIN album_images ai ON ai.artist_name = th.singer AND ai.album_name = th.album
        WHERE track_history_fts MATCH ? AND th.album IS NOT NULL AND th.album != ''
          AND th.singer IS NOT NULL AND th.singer != ''
        GROUP BY th.album, th.singer
        ORDER BY play_count DESC
        """,
        (match,),
    ).fetchall()


def resolve_album_name_variants(
    con: sqlite3.Connection, artist_name: str, album_name: str
) -> list[str]:
    # Spotify sometimes reports a different album_name string for the same
    # release depending on which API path supplied it (e.g. your saved-
    # albums list vs. your streaming history) - a plain "album = ?" match
    # would then miss plays logged under the other spelling entirely. The
    # cover-art background job (src/images/service.py) already resolves a
    # real spotify_album_id per (artist_name, album_name) pair as a side
    # effect of fetching art, so reusing it here to find every album_name
    # variant sharing that id costs zero extra Spotify API calls. Falls
    # back to the literal album_name alone if it was never resolved (e.g.
    # a delisted album, or the image-fetch job hasn't reached it yet).
    row = con.execute(
        "SELECT spotify_album_id FROM album_images WHERE artist_name = ? AND album_name = ?",
        (artist_name, album_name),
    ).fetchone()
    album_id = row["spotify_album_id"] if row else None
    if not album_id:
        return [album_name]
    variants = con.execute(
        "SELECT album_name FROM album_images WHERE artist_name = ? AND spotify_album_id = ?",
        (artist_name, album_id),
    ).fetchall()
    return [r["album_name"] for r in variants] or [album_name]


def load_album_track_history(
    con: sqlite3.Connection, artist_name: str, album_name: str
) -> list[sqlite3.Row]:
    # artist_name is the join key into album_images (see
    # resolve_album_name_variants), so an empty one (a bare /album/{name}
    # link with no ?artist=, which every in-app link always supplies, but
    # an old bookmark or manual URL might not) can't resolve variants -
    # falls back to the original plain album-name match rather than
    # erroring or matching nothing.
    if not artist_name:
        return con.execute(
            "SELECT name, singer, time FROM track_history WHERE album = ? ORDER BY time DESC",
            (album_name,),
        ).fetchall()
    variants = resolve_album_name_variants(con, artist_name, album_name)
    placeholders = ",".join("?" for _ in variants)
    return con.execute(
        f"SELECT name, singer, time FROM track_history "
        f"WHERE singer = ? AND album IN ({placeholders}) ORDER BY time DESC",
        (artist_name, *variants),
    ).fetchall()


def get_album_image(con: sqlite3.Connection, artist_name: str, album_name: str) -> str | None:
    row = con.execute(
        "SELECT image_url FROM album_images WHERE artist_name = ? AND album_name = ?",
        (artist_name, album_name),
    ).fetchone()
    return row["image_url"] if row else None
