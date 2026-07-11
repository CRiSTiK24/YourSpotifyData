from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from src.database import DBDep
from src.html import page, row

from . import service

router = APIRouter(tags=["library"])


@router.get(
    "/liked-songs", response_class=HTMLResponse, status_code=200, description="All liked songs"
)
def liked_songs(con: DBDep):
    tracks = service.load_library_tracks(con)
    rows_html = "".join(
        row(
            t["track_name"],
            f"/track/{quote(t['track_name'])}?artist={quote(t['artist_name'])}",
            t["artist_name"],
            f"/artist/{quote(t['artist_name'])}",
            image_url=t["image_url"],
        )
        for t in tracks
    )
    content = f"""
<a class="back-link" href="/">← Back</a>
<h1>💚 Liked Songs ({len(tracks)})</h1>
<hr class="divider">
{rows_html}
"""
    return page(content)


@router.get(
    "/liked-albums", response_class=HTMLResponse, status_code=200, description="All liked albums"
)
def liked_albums(con: DBDep):
    albums = service.load_library_albums(con)
    rows_html = "".join(
        row(
            a["album_name"],
            f"/album/{quote(a['album_name'])}?artist={quote(a['artist_name'])}",
            a["artist_name"],
            f"/artist/{quote(a['artist_name'])}",
            image_url=a["image_url"],
        )
        for a in albums
    )
    content = f"""
<a class="back-link" href="/">← Back</a>
<h1>💿 Liked Albums ({len(albums)})</h1>
<hr class="divider">
{rows_html}
"""
    return page(content)
