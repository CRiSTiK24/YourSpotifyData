from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.albums.service import get_album_image
from src.database import DBDep
from src.heatmap import build_heatmap_html, resolve_period_filter
from src.html import (
    detail_header,
    detail_layout,
    hero_image,
    link,
    page,
    preview_play_button,
    row,
    spotify_open_button,
)
from src.utils import pluralize

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
    track_uri = next((r["spotify_track_uri"] for r in history if r["spotify_track_uri"]), None)
    spotify_open_html = (
        spotify_open_button(f"https://open.spotify.com/track/{track_uri.rsplit(':', 1)[-1]}")
        if track_uri
        else ""
    )
    album_line = (
        f"<p class='subtitle'>Album: {link(album_name, f'/album/{quote(album_name)}?artist={quote(artist)}')}</p>"
        if album_name
        else ""
    )
    artist_line = (
        f"<p class='subtitle'>Artist: {link(artist, f'/artist/{quote(artist)}')}</p>"
        if artist
        else ""
    )

    heatmap_html, result, base_href = build_heatmap_html(history, f"track_{track_name}", request)
    _, play_count, filter_clear_html = resolve_period_filter(history, result, base_href)

    pl_html = (
        "".join(
            row(pl["name"], f"/playlist/{pl['id']}?name={quote(pl['name'])}") for pl in playlists_in
        )
        or "<p class='info'>Not in any playlist.</p>"
    )

    meta_html = (
        f"{artist_line}{album_line}"
        f"<p class='subtitle'>Played {pluralize(play_count, 'time')}{filter_clear_html}</p>"
    )
    title_html = (
        f"<div class='detail-title-row'><h1>{escape(track_name)}</h1>"
        f"{preview_play_button(track_name, artist, 'detail-play-btn')}</div>"
    )
    header = detail_header(
        title_html,
        meta_html,
        hero_image(get_album_image(con, artist, album_name) if album_name else None),
        heatmap_html,
    )
    return page(
        detail_layout(header, "Playlists", pl_html, list_actions=spotify_open_html),
        title=track_name,
    )
