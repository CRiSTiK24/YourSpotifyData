import sqlite3
from urllib.parse import quote

from src.html import infinite_scroll_trigger, row
from src.utils import format_month_param

from . import service

# Matches library/views.py's MOST_LISTENED_BATCH - the three columns/tabs
# on the merged /most-listened page all page at the same size.
MOST_LISTENED_ARTISTS_BATCH = 30


def most_listened_artists_rows_html(
    con: sqlite3.Connection, offset: int, max_plays: int, start_period: int = 0, end_period: int = 0
) -> str:
    """Fetches one batch + a lookahead row (cheaper than a separate COUNT)
    to know whether to append another infinite-scroll trigger - same shape
    as library/views.py's most_listened_rows_html / _albums_rows_html."""
    artists = service.load_artists(
        con, MOST_LISTENED_ARTISTS_BATCH + 1, offset, start_period, end_period
    )
    has_more = len(artists) > MOST_LISTENED_ARTISTS_BATCH
    artists = artists[:MOST_LISTENED_ARTISTS_BATCH]
    rows_html = "".join(
        row(
            a["singer"],
            f"/artist/{quote(a['singer'])}",
            note=f"×{a['play_count']}",
            image_url=a["image_url"],
            bar_fraction=(a["play_count"] / max_plays) if max_plays else 0,
        )
        for a in artists
    )
    if not rows_html:
        return "<p class='info'>No plays yet.</p>" if offset == 0 else ""
    if has_more:
        next_href = (
            f"/most-listened-artists/more?offset={offset + MOST_LISTENED_ARTISTS_BATCH}"
            f"&max_plays={max_plays}&start_month={format_month_param(start_period) if start_period else ''}"
            f"&end_month={format_month_param(end_period) if end_period else ''}"
        )
        rows_html += infinite_scroll_trigger(next_href)
    return rows_html
