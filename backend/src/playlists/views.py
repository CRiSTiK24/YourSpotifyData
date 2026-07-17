import sqlite3
from urllib.parse import quote

from src.html import card, grid

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
    return f"""
<h1>Playlists ({len(pls)})</h1>
<hr class="divider">
{grid(cards_html)}
"""
