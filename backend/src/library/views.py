import sqlite3
from urllib.parse import quote

from src.html import card, grid

from . import service


def liked_songs_content(con: sqlite3.Connection) -> str:
    tracks = service.load_library_tracks(con)
    cards_html = "".join(
        card(
            t["track_name"],
            f"/track/{quote(t['track_name'])}?artist={quote(t['artist_name'])}",
            t["artist_name"],
            f"/artist/{quote(t['artist_name'])}",
            image_url=t["image_url"],
        )
        for t in tracks
    )
    return f"""
<h1>Liked Songs ({len(tracks)})</h1>
<hr class="divider">
{grid(cards_html)}
"""


def liked_albums_content(con: sqlite3.Connection) -> str:
    albums = service.load_library_albums(con)
    cards_html = "".join(
        card(
            a["album_name"],
            f"/album/{quote(a['album_name'])}?artist={quote(a['artist_name'])}",
            a["artist_name"],
            f"/artist/{quote(a['artist_name'])}",
            image_url=a["image_url"],
        )
        for a in albums
    )
    return f"""
<h1>Liked Albums ({len(albums)})</h1>
<hr class="divider">
{grid(cards_html)}
"""
