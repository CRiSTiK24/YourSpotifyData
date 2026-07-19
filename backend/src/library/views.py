import sqlite3
from urllib.parse import quote

from src.html import card, copy_list_button, grid, page_header

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
    export_lines = [f"{t['track_name']} - {t['artist_name']}" for t in tracks]
    header = page_header(
        f"Liked Songs ({len(tracks)})",
        copy_list_button(export_lines, "liked-songs-list"),
    )
    return f"""
{header}
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
    export_lines = [f"{a['album_name']} - {a['artist_name']}" for a in albums]
    header = page_header(
        f"Liked Albums ({len(albums)})",
        copy_list_button(export_lines, "liked-albums-list"),
    )
    return f"""
{header}
<hr class="divider">
{grid(cards_html)}
"""
