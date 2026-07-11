from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.database import DBDep
from src.heatmap import build_heatmap_html
from src.html import page, row

from . import service

router = APIRouter(tags=["tracks"])


@router.get(
    "/track/{track_name}",
    response_class=HTMLResponse,
    status_code=200,
    description="Track detail with play history",
)
def track_detail(track_name: str, request: Request, con: DBDep, artist: str = ""):
    history = service.load_track_history(con, track_name, artist)
    playlists_in = service.load_track_playlists(con, track_name, artist)

    album_name = next((r["album"] for r in history if r["album"]), None)
    album_link = (
        f"<a class='artist-link' href='/album/{quote(album_name)}?artist={quote(artist)}'>"
        f"💿 {escape(album_name)}</a>"
        if album_name
        else ""
    )
    artist_link = (
        f"<a class='artist-link' href='/artist/{quote(artist)}'>🎤 {escape(artist)}</a>"
        if artist
        else ""
    )

    heatmap_html, _ = build_heatmap_html(history, f"track_{track_name}", request)

    pl_html = (
        "".join(
            row(pl["name"], f"/playlist/{pl['id']}?name={quote(pl['name'])}") for pl in playlists_in
        )
        or "<p class='info'>Not in any playlist.</p>"
    )

    content = f"""
<a class="back-link" href="javascript:history.back()">← Back</a>
<h1>🎵 {escape(track_name)}</h1>
{artist_link} {album_link}
<p class="subtitle">Played {len(history)} time{"s" if len(history) != 1 else ""}</p>
<hr class="divider">
{heatmap_html}
<hr class="divider">
<h2>📋 Playlists</h2>
{pl_html}
"""
    return page(content)
