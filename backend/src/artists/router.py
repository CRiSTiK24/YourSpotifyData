from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.constants import MONTHS
from src.database import DBDep
from src.heatmap import build_heatmap_html
from src.html import card, detail_layout, grid, hero_image, infinite_scroll_trigger, page, row
from src.utils import aggregate_plays

from . import service
from .exceptions import ArtistNotFound
from .views import artist_rows_html, artists_content

router = APIRouter(tags=["artists"])

ARTIST_TRACKS_BATCH = 20


def _artist_tracks_html(con, artist_name: str, offset: int) -> str:
    """Returns raw cards (+ a trailing infinite-scroll sentinel) with no
    grid wrapper - the initial page render wraps this in grid() itself,
    but the /tracks pagination fragment below must NOT be re-wrapped, since
    it replaces the sentinel's outerHTML and needs its cards to land as
    direct children of the *existing* grid for the CSS grid layout to
    apply to them."""
    tracks = service.load_artist_tracks_page(con, artist_name, offset, ARTIST_TRACKS_BATCH)
    has_more = len(tracks) > ARTIST_TRACKS_BATCH
    tracks = tracks[:ARTIST_TRACKS_BATCH]
    cards_html = "".join(
        card(
            t["name"],
            f"/track/{quote(t['name'])}?artist={quote(artist_name)}",
            note=f"×{t['cnt']}",
            image_url=t["image_url"],
        )
        for t in tracks
    )
    if has_more:
        next_href = f"/artist/{quote(artist_name)}/tracks?offset={offset + ARTIST_TRACKS_BATCH}"
        cards_html += infinite_scroll_trigger(next_href)
    return cards_html


@router.get(
    "/artists", response_class=HTMLResponse, status_code=200, description="Browse all artists"
)
def artists(con: DBDep, query: str = "", artists_page: int = 1):
    return page(artists_content(con, query, artists_page))


@router.get(
    "/artists/rows",
    response_class=HTMLResponse,
    status_code=200,
    description="Infinite-scroll fragment: next batch of artist rows",
)
def artists_rows(con: DBDep, query: str = "", artists_page: int = 1):
    all_artists = list(service.search_artists(con, query) if query else service.load_artists(con))
    return HTMLResponse(artist_rows_html(all_artists, query, artists_page))


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

    tracks_html = grid(_artist_tracks_html(con, artist_name, 0), compact=True)

    header = f"""
{hero_image(service.get_artist_image(con, artist_name))}
<h1>{escape(artist_name)}</h1>
<p class="subtitle">{len(history)} total plays</p>
"""
    return page(
        detail_layout(
            header, heatmap_html + period_html, "Tracks", tracks_html, list_id="artist-tracks"
        )
    )


@router.get(
    "/artist/{artist_name}/tracks",
    response_class=HTMLResponse,
    status_code=200,
    description="Infinite-scroll fragment: next batch of an artist's tracks",
)
def artist_tracks(artist_name: str, con: DBDep, offset: int = 0):
    return HTMLResponse(_artist_tracks_html(con, artist_name, offset))
