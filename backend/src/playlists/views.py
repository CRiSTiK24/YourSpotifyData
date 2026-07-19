import sqlite3
from urllib.parse import quote

from src.html import card, copy_list_button, grid, page_header

from . import service


def playlists_content(con: sqlite3.Connection) -> str:
    pls = service.load_playlists(con)
    cards_html = "".join(
        card(
            pl["name"],
            f"/playlist/{pl['id']}?name={quote(pl['name'])}",
            image_url=pl["image_url"],
        )
        for pl in pls
    )
    export_lines = []
    for pl in pls:
        export_lines.append(pl["name"])
        for t in service.load_playlist_tracks(con, pl["id"]):
            export_lines.append(f"  * {t['track_name']} - {t['artist_name']}")
        export_lines.append("")
    header = page_header(
        f"Playlists ({len(pls)})",
        copy_list_button(export_lines, "playlists-list"),
    )
    return f"""
{header}
<hr class="divider">
{grid(cards_html)}
"""
