from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.database import DBDep
from src.heatmap import build_heatmap_html, resolve_period_filter
from src.html import (
    detail_header,
    detail_layout,
    hero_image,
    link,
    page,
    row,
    spotify_open_button,
    u,
)
from src.users import service as users_service
from src.utils import aggregate_plays, pluralize

from . import service

router = APIRouter(tags=["albums"])


@router.get(
    "/album/{album_name}",
    response_class=HTMLResponse,
    status_code=200,
    description="Album detail with play history",
)
def album_detail(
    album_name: str,
    request: Request,
    con: DBDep,
    viewed_user: users_service.ViewedUserDep,
    artist: str = "",
):
    user_id = viewed_user["id"] if viewed_user else None
    history = service.load_album_track_history(con, user_id, artist, album_name)

    heatmap_html, result, base_href = build_heatmap_html(history, f"album_{album_name}", request)

    plays, play_count, filter_clear_html = resolve_period_filter(history, result, base_href)
    aggregated = aggregate_plays(plays)
    tracks_html = "".join(
        row(
            name,
            u(f"/track/{quote(name)}?artist={quote(singer or artist)}"),
            note=str(count),
            preview_artist=singer or artist,
        )
        for name, singer, count in aggregated
    )

    artist_line = (
        f"<p class='subtitle'>Artist: {link(artist, u(f'/artist/{quote(artist)}'))}</p>"
        if artist
        else ""
    )

    meta_html = (
        f"{artist_line}"
        f"<p class='subtitle'>{pluralize(play_count, 'play')} "
        f"from this album{filter_clear_html}</p>"
    )
    header = detail_header(
        f"<h1>{escape(album_name)}</h1>",
        meta_html,
        hero_image(service.get_album_image(con, artist, album_name), large=True),
        heatmap_html,
    )
    album_id = service.get_album_spotify_id(con, artist, album_name)
    spotify_open_html = (
        spotify_open_button(f"https://open.spotify.com/album/{album_id}") if album_id else ""
    )
    return page(
        detail_layout(header, "Tracks", tracks_html, list_actions=spotify_open_html),
        title=album_name,
    )
