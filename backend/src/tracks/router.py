from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.albums.service import get_album_image
from src.database import DBDep
from src.heatmap import build_heatmap_html
from src.html import detail_layout, hero_image, link, page, row

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
    album_line = (
        f"<p class='subtitle'>Album: {link(album_name, f'/album/{quote(album_name)}?artist={quote(artist)}')}</p>"
        if album_name
        else ""
    )
    artist_line = (
        f"<p class='subtitle'>Artist: {link(artist, f'/artist/{quote(artist)}')}</p>" if artist else ""
    )

    heatmap_html, _ = build_heatmap_html(history, f"track_{track_name}", request)

    pl_html = (
        "".join(
            row(pl["name"], f"/playlist/{pl['id']}?name={quote(pl['name'])}") for pl in playlists_in
        )
        or "<p class='info'>Not in any playlist.</p>"
    )

    header = f"""
{hero_image(get_album_image(con, artist, album_name) if album_name else None)}
<h1>{escape(track_name)}</h1>
{artist_line}
{album_line}
<p class="subtitle">Played {len(history)} time{"s" if len(history) != 1 else ""}</p>
"""
    return page(detail_layout(header, heatmap_html, "Playlists", pl_html))
