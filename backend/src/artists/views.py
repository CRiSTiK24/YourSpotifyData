import sqlite3
from urllib.parse import quote

from src.html import paginated_fragment, row, u
from src.utils import most_listened_next_href

from . import service

MOST_LISTENED_ARTISTS_BATCH = 30


def most_listened_artists_rows_html(
    con: sqlite3.Connection,
    user_id: int,
    offset: int,
    max_plays: int,
    start_period: int = 0,
    end_period: int = 0,
    genre: str = "",
) -> str:
    artists = service.load_artists(
        con, user_id, MOST_LISTENED_ARTISTS_BATCH + 1, offset, start_period, end_period, genre
    )
    has_more = len(artists) > MOST_LISTENED_ARTISTS_BATCH
    artists = artists[:MOST_LISTENED_ARTISTS_BATCH]
    rows_html = "".join(
        row(
            a["singer"],
            u(f"/artist/{quote(a['singer'])}"),
            note=str(a["play_count"]),
            image_url=a["image_url"],
        )
        for a in artists
    )
    next_href = most_listened_next_href(
        u("/most-listened-artists/more"),
        offset + MOST_LISTENED_ARTISTS_BATCH,
        max_plays,
        start_period,
        end_period,
        genre,
    )
    return paginated_fragment(
        rows_html,
        offset=offset,
        has_more=has_more,
        next_href=next_href,
        empty_message="<p class='info'>No plays yet.</p>",
    )
