from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.albums.service import get_album_image
from src.database import DBDep
from src.heatmap import build_heatmap_html, period_label
from src.html import detail_header, detail_layout, filter_clear_link, hero_image, link, page, row

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

    heatmap_html, result, base_href = build_heatmap_html(history, f"track_{track_name}", request)

    filter_clear_html = ""
    if result:
        _, _, _, plays = result
        play_count = len(plays)
        filter_clear_html = filter_clear_link(period_label(result), base_href)
    else:
        play_count = len(history)

    pl_html = (
        "".join(
            row(pl["name"], f"/playlist/{pl['id']}?name={quote(pl['name'])}") for pl in playlists_in
        )
        or "<p class='info'>Not in any playlist.</p>"
    )

    meta_html = (
        f"{artist_line}{album_line}"
        f"<p class='subtitle'>Played {play_count} time{'s' if play_count != 1 else ''}{filter_clear_html}</p>"
    )
    header = detail_header(
        f"<h1>{escape(track_name)}</h1>",
        meta_html,
        hero_image(get_album_image(con, artist, album_name) if album_name else None),
        heatmap_html,
    )
    return page(detail_layout(header, "Playlists", pl_html), title=track_name)
