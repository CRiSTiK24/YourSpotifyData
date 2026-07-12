from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.constants import MONTHS
from src.database import DBDep
from src.heatmap import build_heatmap_html
from src.html import back_link, detail_layout, hero_image, page, row
from src.utils import aggregate_plays

from . import service
from .exceptions import ArtistNotFound
from .views import artists_content

router = APIRouter(tags=["artists"])


@router.get(
    "/artists", response_class=HTMLResponse, status_code=200, description="Browse all artists"
)
def artists(con: DBDep, query: str = "", artists_page: int = 1):
    return page(artists_content(con, query, artists_page))


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
            t["name"],
            f"/track/{quote(t['name'])}?artist={quote(artist_name)}",
            note=f"×{t['cnt']}",
            image_url=t["image_url"],
        )
        for t in top_tracks
    )

    header = f"""
{back_link("/artists")}
{hero_image(service.get_artist_image(con, artist_name))}
<h1>{escape(artist_name)}</h1>
<p class="subtitle">{len(history)} total plays</p>
"""
    return page(detail_layout(header, heatmap_html + period_html, "Top tracks", top_html))
