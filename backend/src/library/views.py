import sqlite3
from urllib.parse import quote

from src.html import back_link, row

from . import service


def liked_songs_content(con: sqlite3.Connection) -> str:
    tracks = service.load_library_tracks(con)
    rows_html = "".join(
        row(
            t["track_name"],
            f"/track/{quote(t['track_name'])}?artist={quote(t['artist_name'])}",
            t["artist_name"],
            f"/artist/{quote(t['artist_name'])}",
            image_url=t["image_url"],
        )
        for t in tracks
    )
    return f"""
{back_link("/")}
<h1>Liked Songs ({len(tracks)})</h1>
<hr class="divider">
{rows_html}
"""


def liked_albums_content(con: sqlite3.Connection) -> str:
    albums = service.load_library_albums(con)
    rows_html = "".join(
        row(
            a["album_name"],
            f"/album/{quote(a['album_name'])}?artist={quote(a['artist_name'])}",
            a["artist_name"],
            f"/artist/{quote(a['artist_name'])}",
            image_url=a["image_url"],
        )
        for a in albums
    )
    return f"""
{back_link("/")}
<h1>Liked Albums ({len(albums)})</h1>
<hr class="divider">
{rows_html}
"""
