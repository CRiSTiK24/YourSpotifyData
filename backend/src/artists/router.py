from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.constants import MONTHS
from src.database import DBDep
from src.heatmap import build_heatmap_html
from src.html import page, paginate, pagination_html, row
from src.utils import aggregate_plays

from . import service
from .exceptions import ArtistNotFound

router = APIRouter(tags=["artists"])


@router.get(
    "/artists", response_class=HTMLResponse, status_code=200, description="Browse all artists"
)
def artists(request: Request, con: DBDep, query: str = "", artists_page: int = 1):
    all_artists = service.search_artists(con, query) if query else service.load_artists(con)

    page_items, current_page, total_pages = paginate(list(all_artists), artists_page)

    rows_html = "".join(
        row(a["singer"], f"/artist/{quote(a['singer'])}", note=f"{a['play_count']} plays")
        for a in page_items
    )
    base = f"/artists?query={quote(query)}" if query else "/artists"
    pag = pagination_html(current_page, total_pages, base, "artists_page")

    content = f"""
<a class="back-link" href="/">← Back</a>
<h1>🎤 Artists</h1>
<form class="search-form" action="/artists" method="get">
  <input name="query" type="text" value="{escape(query)}" placeholder="Search artists…">
  <button type="submit">Search</button>
</form>
<hr class="divider">
{rows_html}
{pag}
<p class="subtitle">{len(all_artists)} artists total</p>
"""
    return page(content)


@router.get(
    "/artist/{artist_name}",
    response_class=HTMLResponse,
    status_code=200,
    description="Artist detail with play history",
)
def artist_detail(artist_name: str, request: Request, con: DBDep):
    history = service.load_artist_history(con, artist_name)
    if not history:
        raise ArtistNotFound(artist_name)

    top_tracks = service.load_artist_top_tracks(con, artist_name)

    heatmap_html, result = build_heatmap_html(history, f"artist_{artist_name}", request)

    period_html = ""
    if result:
        year, month, day, plays = result
        label = f"{MONTHS[month - 1]} {day}, {year}" if day else f"{MONTHS[month - 1]} {year}"
        aggregated = aggregate_plays(plays)
        period_html = (
            f"<h2>{label} — {len(plays)} play{'s' if len(plays) != 1 else ''} "
            f"across {len(aggregated)} track{'s' if len(aggregated) != 1 else ''}</h2>"
        )
        period_html += "".join(
            row(name, f"/track/{quote(name)}?artist={quote(artist_name)}", note=f"×{count}")
            for name, _, count in aggregated
        )

    top_html = "".join(
        row(
            t["name"], f"/track/{quote(t['name'])}?artist={quote(artist_name)}", note=f"×{t['cnt']}"
        )
        for t in top_tracks
    )

    content = f"""
<a class="back-link" href="/artists">← Back</a>
<h1>🎤 {escape(artist_name)}</h1>
<p class="subtitle">{len(history)} total plays</p>
<hr class="divider">
{heatmap_html}
{period_html}
<hr class="divider">
<h2>Top tracks</h2>
{top_html}
"""
    return page(content)
