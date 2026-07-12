from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.database import DBDep
from src.heatmap import build_heatmap_html
from src.html import back_link, page, paginate, pagination_html, row
from src.utils import aggregate_plays

from . import service

router = APIRouter(tags=["search"])


@router.get(
    "/search",
    response_class=HTMLResponse,
    status_code=200,
    description="Search across tracks, albums and playlists",
)
def search(request: Request, con: DBDep, query: str = "", search_page: int = 1):
    if not query:
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url="/", status_code=302)

    history = service.search_track_history(con, query)
    lib_tracks = service.search_library_tracks(con, query)
    lib_albums = service.search_library_albums(con, query)
    playlist_rows = service.search_playlists(con, query)
    pl_ids = {r["name"]: r["id"] for r in con.execute("SELECT id, name FROM playlists").fetchall()}

    aggregated = aggregate_plays([{"name": r["name"], "singer": r["singer"]} for r in history])
    page_items, current_page, total_pages = paginate(aggregated, search_page)

    rows_html = "".join(
        row(
            name,
            f"/track/{quote(name)}?artist={quote(singer or '')}",
            singer,
            f"/artist/{quote(singer)}" if singer else None,
            note=f"×{count}",
        )
        for name, singer, count in page_items
    )
    pag = pagination_html(current_page, total_pages, f"/search?query={quote(query)}", "search_page")
    heatmap_html, _ = build_heatmap_html(history, f"search_{query}", request)

    liked_rows = (
        "".join(
            row(
                r["track_name"],
                f"/track/{quote(r['track_name'])}?artist={quote(r['artist_name'])}",
                r["artist_name"],
                f"/artist/{quote(r['artist_name'])}",
                image_url=r["image_url"],
            )
            for r in lib_tracks
        )
        or "<p class='info'>Not in your liked songs.</p>"
    )

    albums_section = ""
    if lib_albums:
        albums_section = "<h2>Liked albums</h2>" + "".join(
            row(
                r["album_name"],
                f"/album/{quote(r['album_name'])}?artist={quote(r['artist_name'])}",
                r["artist_name"],
                f"/artist/{quote(r['artist_name'])}",
                image_url=r["image_url"],
            )
            for r in lib_albums
        )

    by_playlist: dict[str, list] = {}
    for r in playlist_rows:
        by_playlist.setdefault(r["playlist_name"], []).append(r)

    pl_html = ""
    for pl_name, tracks in by_playlist.items():
        pl_id = pl_ids.get(pl_name, "")
        inner = (
            f"<div class='row'><a href='/playlist/{pl_id}?name={quote(pl_name)}'>"
            f"Open {escape(pl_name)}</a></div>"
            if pl_id
            else ""
        ) + "".join(
            row(
                t["track_name"],
                f"/track/{quote(t['track_name'])}?artist={quote(t['artist_name'])}",
                t["artist_name"],
                f"/artist/{quote(t['artist_name'])}",
                image_url=t["image_url"],
            )
            for t in tracks
        )
        pl_html += (
            f"<details style='margin-bottom:8px'>"
            f"<summary style='cursor:pointer;padding:6px 0'>"
            f"{escape(pl_name)} ({len(tracks)} match{'es' if len(tracks) > 1 else ''})"
            f"</summary>{inner}</details>"
        )

    content = f"""
{back_link("/")}
<h1>Search: &ldquo;{escape(query)}&rdquo;</h1>
<h2>Play history — {len(history)} plays across {len(aggregated)} track{"s" if len(aggregated) != 1 else ""}</h2>
{rows_html or "<p class='info'>No play history found.</p>"}
{pag}
<h2>Listen history heatmap</h2>
{heatmap_html}
<hr class="divider">
<h2>Liked songs ({len(lib_tracks)})</h2>
{liked_rows}
{albums_section}
<hr class="divider">
<h2>Playlists ({len(playlist_rows)} matches)</h2>
{pl_html or "<p class='info'>Not found in any playlist.</p>"}
"""
    return page(content)
