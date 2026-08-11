from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from src.albums import service as albums_service
from src.artists import service as artists_service
from src.database import DBDep
from src.html import paginated_fragment, row
from src.utils import aggregate_plays

from . import service

router = APIRouter(tags=["search"])

QUICK_RESULTS_BATCH = 8


def _quick_track_results_html(con, query: str, offset: int = 0) -> str:
    history = service.search_track_history_by_name(con, query)
    aggregated = aggregate_plays([{"name": r["name"], "singer": r["singer"]} for r in history])
    batch = aggregated[offset : offset + QUICK_RESULTS_BATCH]
    rows_html = "".join(
        row(
            name,
            f"/track/{quote(name)}?artist={quote(singer or '')}",
            note=str(count),
            preview_artist=singer,
        )
        for name, singer, count in batch
    )
    return paginated_fragment(
        rows_html,
        offset=offset,
        has_more=offset + QUICK_RESULTS_BATCH < len(aggregated),
        next_href=f"/search/more?kind=tracks&query={quote(query)}&offset={offset + QUICK_RESULTS_BATCH}",
        empty_message="<p class='info'>No matches.</p>",
    )


def _quick_artist_results_html(con, query: str, offset: int = 0) -> str:
    artists = list(artists_service.search_artists(con, query))
    batch = artists[offset : offset + QUICK_RESULTS_BATCH]
    rows_html = "".join(
        row(
            a["singer"],
            f"/artist/{quote(a['singer'])}",
            note=f"{a['play_count']} plays",
            image_url=a["image_url"],
        )
        for a in batch
    )
    return paginated_fragment(
        rows_html,
        offset=offset,
        has_more=offset + QUICK_RESULTS_BATCH < len(artists),
        next_href=f"/search/more?kind=artists&query={quote(query)}&offset={offset + QUICK_RESULTS_BATCH}",
        empty_message="<p class='info'>No matches.</p>",
    )


def _quick_album_results_html(con, query: str, offset: int = 0) -> str:
    albums = list(albums_service.search_albums(con, query))
    batch = albums[offset : offset + QUICK_RESULTS_BATCH]
    rows_html = "".join(
        row(
            a["album"],
            f"/album/{quote(a['album'])}?artist={quote(a['singer'])}",
            note=f"{a['play_count']} plays",
            image_url=a["image_url"],
        )
        for a in batch
    )
    return paginated_fragment(
        rows_html,
        offset=offset,
        has_more=offset + QUICK_RESULTS_BATCH < len(albums),
        next_href=f"/search/more?kind=albums&query={quote(query)}&offset={offset + QUICK_RESULTS_BATCH}",
        empty_message="<p class='info'>No matches.</p>",
    )


def _quick_results_html(con, query: str) -> str:
    tracks_html = _quick_track_results_html(con, query)
    artists_html = _quick_artist_results_html(con, query)
    albums_html = _quick_album_results_html(con, query)
    return f"""
<div class="qs-tabs">
  <button type="button" class="qs-tab active" data-qs-tab="tracks">Tracks</button>
  <button type="button" class="qs-tab" data-qs-tab="artists">Artists</button>
  <button type="button" class="qs-tab" data-qs-tab="albums">Albums</button>
</div>
<div class="qs-results-grid">
  <div class="qs-column" data-qs-panel="tracks">
    <h4 class="qs-column-title">Tracks</h4>
    {tracks_html}
  </div>
  <div class="qs-column" data-qs-panel="artists" hidden>
    <h4 class="qs-column-title">Artists</h4>
    {artists_html}
  </div>
  <div class="qs-column" data-qs-panel="albums" hidden>
    <h4 class="qs-column-title">Albums</h4>
    {albums_html}
  </div>
</div>
"""


@router.get(
    "/search",
    response_class=HTMLResponse,
    status_code=200,
    description="Live quick-search fragment for the persistent chrome search box "
    "(desktop topbar + mobile topbar) - tabbed Tracks/Artists, no navigation",
)
def quick_search(con: DBDep, query: str = ""):
    query = query.strip()
    return HTMLResponse(_quick_results_html(con, query) if query else "")


@router.get(
    "/search/more",
    response_class=HTMLResponse,
    status_code=200,
    description="Infinite-scroll fragment: next batch of quick-search results for one tab",
)
def quick_search_more(con: DBDep, query: str = "", offset: int = 0, kind: str = "tracks"):
    query = query.strip()
    if kind == "artists":
        return HTMLResponse(_quick_artist_results_html(con, query, offset))
    if kind == "albums":
        return HTMLResponse(_quick_album_results_html(con, query, offset))
    return HTMLResponse(_quick_track_results_html(con, query, offset))
