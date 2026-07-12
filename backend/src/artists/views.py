import sqlite3
from urllib.parse import quote

from src.html import back_link, paginate, pagination_html, row, search_form

from . import service


def artists_content(con: sqlite3.Connection, query: str = "", artists_page: int = 1) -> str:
    all_artists = service.search_artists(con, query) if query else service.load_artists(con)

    page_items, current_page, total_pages = paginate(list(all_artists), artists_page)

    rows_html = "".join(
        row(
            a["singer"],
            f"/artist/{quote(a['singer'])}",
            note=f"{a['play_count']} plays",
            image_url=a["image_url"],
        )
        for a in page_items
    )
    base = f"/artists?query={quote(query)}" if query else "/artists"
    pag = pagination_html(current_page, total_pages, base, "artists_page")

    return f"""
{back_link("/")}
<h1>Artists</h1>
{search_form("/artists", "Search artists…", value=query, autofocus=False)}
<hr class="divider">
{rows_html}
{pag}
<p class="subtitle">{len(all_artists)} artists total</p>
"""
