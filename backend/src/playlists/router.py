from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.constants import MONTHS
from src.database import DBDep
from src.heatmap import build_heatmap_html
from src.html import detail_layout, hero_image, page, row
from src.utils import aggregate_plays

from . import service
from .exceptions import PlaylistNotFound
from .views import playlists_content

router = APIRouter(tags=["playlists"])


@router.get("/playlists", response_class=HTMLResponse, status_code=200, description="All playlists")
def playlists(con: DBDep):
    return page(playlists_content(con))


@router.get(
    "/playlist/{playlist_id}",
    response_class=HTMLResponse,
    status_code=200,
    description="Playlist detail with play history",
)
def playlist_detail(playlist_id: int, request: Request, con: DBDep, name: str = ""):
    if not service.playlist_exists(con, playlist_id):
        raise PlaylistNotFound(playlist_id)

    tracks = service.load_playlist_tracks(con, playlist_id)
    history = service.load_playlist_history(con, playlist_id)

    heatmap_html, result = build_heatmap_html(history, f"playlist_{playlist_id}", request)

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
                n,
                f"/track/{quote(n)}?artist={quote(s or '')}",
                s,
                f"/artist/{quote(s)}" if s else None,
                note=f"×{c}",
            )
            for n, s, c in aggregated
        )

    tracks_html = "".join(
        row(
            t["track_name"],
            f"/track/{quote(t['track_name'])}?artist={quote(t['artist_name'])}",
            t["artist_name"],
            f"/artist/{quote(t['artist_name'])}",
            image_url=t["image_url"],
        )
        for t in tracks
    )

    header = f"""
{hero_image(service.get_playlist_image(con, playlist_id))}
<h1>{escape(name)}</h1>
<p class="subtitle">{len(tracks)} track{"s" if len(tracks) != 1 else ""} &nbsp;·&nbsp; {len(history)} total plays</p>
"""
    return page(detail_layout(header, heatmap_html + period_html, "Tracks", tracks_html))
