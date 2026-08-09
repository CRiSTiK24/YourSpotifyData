import sqlite3

from src.utils import fts_match_query


def search_albums(con: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    """Same (album, singer) grouping/ranking as most_listened_albums, just
    filtered to albums matching query - the quick-search Albums tab.
    FTS instead of a LIKE scan, same reasoning as search_track_history -
    track_history is 200k+ rows and growing. Restricted to the album
    column so this only matches on the album's own title, not the artist -
    a query matching only the artist shouldn't surface every album by that
    artist here (that's what the Artists tab is for)."""
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
