import sqlite3
from html import unescape
from urllib.parse import quote

from src.html import card, copy_list_button, grid, page_header, u

from . import service


def playlists_content(con: sqlite3.Connection, user_id: int) -> str:
    pls = service.load_playlists(con, user_id)
    cards_html = "".join(
        card(
            pl["name"],
            u(f"/playlist/{pl['id']}?name={quote(pl['name'])}"),
            image_url=pl["image_url"],
            hover_tooltip=unescape(pl["description"]) if pl["description"] else None,
            raw_cover=True,
        )
        for pl in pls
    )
    export_lines = []
    for pl in pls:
        export_lines.append(pl["name"])
        if pl["description"]:
            export_lines.append(unescape(pl["description"]))
        for t in service.load_playlist_tracks(con, user_id, pl["id"]):
            export_lines.append(f"  * {t['track_name']} - {t['artist_name']}")
        export_lines.append("")
    header = page_header(
        f"Playlists ({len(pls)})",
        copy_list_button(export_lines, "playlists-list"),
    )
    rules_html = """
<ul class="subtitle">
<li>A song can only stay if I can hear it and resonate just by playing it in my mind.</li>
<li>No duplicate artists, however if it's a collaboration it counts as a different one</li>
<li>All songs need to share the aesthetic. This one is pretty personal as I end up merging
lot's of genres if it feels right to me.</li>
<li>It's a living thing! I will remove songs I no longer think they are amazing no matter
how much I loved them in the past. VERY HARD to remove those, but we gotta do what we
gotta do :(</li>
</ul>"""
    return f"""
{header}
{rules_html}
<hr class="divider">
{grid(cards_html)}
"""
