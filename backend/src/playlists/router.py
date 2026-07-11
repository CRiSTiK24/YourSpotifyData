from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.constants import MONTHS
from src.database import DBDep
from src.heatmap import build_heatmap_html
from src.html import page, row
from src.utils import aggregate_plays

from . import service
from .exceptions import PlaylistNotFound

router = APIRouter(tags=["playlists"])


@router.get("/playlists", response_class=HTMLResponse, status_code=200, description="All playlists")
def playlists(con: DBDep):
    pls = service.load_playlists(con)
    rows_html = "".join(
        row(pl["name"], f"/playlist/{pl['id']}?name={quote(pl['name'])}") for pl in pls
    )
    content = f"""
<a class="back-link" href="/">← Back</a>
<h1>📋 Playlists ({len(pls)})</h1>
<hr class="divider">
{rows_html}
"""
    return page(content)


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
        )
        for t in tracks
    )

    content = f"""
<a class="back-link" href="/playlists">← Back</a>
<h1>📋 {escape(name)}</h1>
<p class="subtitle">{len(tracks)} track{"s" if len(tracks) != 1 else ""} &nbsp;·&nbsp; {len(history)} total plays</p>
<hr class="divider">
{heatmap_html}
{period_html}
<hr class="divider">
<h2>Tracks</h2>
{tracks_html}
"""
    return page(content)
