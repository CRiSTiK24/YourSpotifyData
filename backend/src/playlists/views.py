import sqlite3
from urllib.parse import quote

from src.html import row

from . import service


def playlists_content(con: sqlite3.Connection) -> str:
    pls = service.load_playlists(con)
    rows_html = "".join(
        row(pl["name"], f"/playlist/{pl['id']}?name={quote(pl['name'])}") for pl in pls
    )
    return f"""
<h1>Playlists ({len(pls)})</h1>
<hr class="divider">
{rows_html}
"""
