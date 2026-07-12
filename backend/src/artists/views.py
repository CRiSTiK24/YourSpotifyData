import sqlite3
from urllib.parse import quote

from src.html import infinite_scroll_trigger, paginate, row, search_form

from . import service


def artist_rows_html(all_artists: list, query: str, artists_page: int) -> str:
    page_items, current_page, total_pages = paginate(all_artists, artists_page)
    rows_html = "".join(
        row(
            a["singer"],
            f"/artist/{quote(a['singer'])}",
            note=f"{a['play_count']} plays",
            image_url=a["image_url"],
        )
        for a in page_items
    )
    if current_page < total_pages:
        next_href = f"/artists/rows?query={quote(query)}&artists_page={current_page + 1}"
        rows_html += infinite_scroll_trigger(next_href)
    return rows_html


def artists_content(con: sqlite3.Connection, query: str = "", artists_page: int = 1) -> str:
    all_artists = list(service.search_artists(con, query) if query else service.load_artists(con))
    rows_html = artist_rows_html(all_artists, query, artists_page)

    return f"""
<h1>Artists</h1>
{search_form("/artists", "Search artists…", value=query, autofocus=False)}
<hr class="divider">
<div id="artist-rows">{rows_html}</div>
<p class="subtitle">{len(all_artists)} artists total</p>
"""
