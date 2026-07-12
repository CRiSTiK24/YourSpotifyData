from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.constants import MONTHS
from src.database import DBDep
from src.heatmap import build_heatmap_html
from src.html import detail_layout, hero_image, link, page, row
from src.utils import aggregate_plays

from . import service

router = APIRouter(tags=["albums"])


@router.get(
    "/album/{album_name}",
    response_class=HTMLResponse,
    status_code=200,
    description="Album detail with play history",
)
def album_detail(album_name: str, request: Request, con: DBDep, artist: str = ""):
    history = service.load_album_track_history(con, album_name)

    heatmap_html, result = build_heatmap_html(history, f"album_{album_name}", request)

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
            row(
                name,
                f"/track/{quote(name)}?artist={quote(singer or artist)}",
                singer or artist,
                f"/artist/{quote(singer or artist)}" if (singer or artist) else None,
                note=f"×{count}",
            )
            for name, singer, count in aggregated
        )

    tracks_html = "".join(
        row(
            name,
            f"/track/{quote(name)}?artist={quote(singer or artist)}",
            singer or artist,
            f"/artist/{quote(singer or artist)}" if (singer or artist) else None,
            note=f"×{count}",
        )
        for name, singer, count in aggregate_plays(history)
    )

    artist_line = (
        f"<p class='subtitle'>Artist: {link(artist, f'/artist/{quote(artist)}')}</p>" if artist else ""
    )

    header = f"""
{hero_image(service.get_album_image(con, artist, album_name))}
<h1>{escape(album_name)}</h1>
{artist_line}
<p class="subtitle">{len(history)} plays from this album</p>
"""
    return page(detail_layout(header, heatmap_html + period_html, "Tracks", tracks_html))
