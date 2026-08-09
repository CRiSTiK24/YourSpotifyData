from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.database import DBDep
from src.heatmap import build_heatmap_html, period_label
from src.html import (
    card,
    detail_header,
    detail_layout,
    filter_clear_link,
    grid,
    hero_image,
    infinite_scroll_trigger,
    page,
)
from src.utils import aggregate_plays, parse_month_param

from . import service
from .exceptions import ArtistNotFound
from .views import most_listened_artists_rows_html

router = APIRouter(tags=["artists"])

ARTIST_TRACKS_BATCH = 20


def _artist_tracks_html(con, artist_name: str, offset: int) -> str:
    """Returns raw cards (+ a trailing infinite-scroll sentinel) with no
    grid wrapper - the initial page render wraps this in grid() itself,
    but the /tracks pagination fragment below must NOT be re-wrapped, since
    it replaces the sentinel's outerHTML and needs its cards to land as
    direct children of the *existing* grid for the CSS grid layout to
    apply to them."""
    tracks = service.load_artist_tracks_page(con, artist_name, offset, ARTIST_TRACKS_BATCH)
    has_more = len(tracks) > ARTIST_TRACKS_BATCH
    tracks = tracks[:ARTIST_TRACKS_BATCH]
    cards_html = "".join(
        card(
            t["name"],
            f"/track/{quote(t['name'])}?artist={quote(artist_name)}",
            note=f"×{t['cnt']}",
            image_url=t["image_url"],
        )
        for t in tracks
    )
    if has_more:
        next_href = f"/artist/{quote(artist_name)}/tracks?offset={offset + ARTIST_TRACKS_BATCH}"
        cards_html += infinite_scroll_trigger(next_href)
    return cards_html


@router.get(
    "/artists",
    status_code=302,
    description="Artist browsing merged into /most-listened (Artists tab/column)",
)
def artists_redirect():
    return RedirectResponse(url="/most-listened", status_code=302)


@router.get(
    "/most-listened-artists/more",
    response_class=HTMLResponse,
    status_code=200,
    description="Infinite-scroll fragment: next batch of most-listened-artists rows",
)
def most_listened_artists_more(
    con: DBDep, offset: int = 0, max_plays: int = 0, start_month: str = "", end_month: str = ""
):
    return HTMLResponse(
        most_listened_artists_rows_html(
            con, offset, max_plays, parse_month_param(start_month), parse_month_param(end_month)
        )
    )


@router.get(
    "/artist/{artist_name}",
    response_class=HTMLResponse,
    status_code=200,
    description="Artist detail with play history",
)
def artist_detail(artist_name: str, request: Request, con: DBDep):
    history = service.load_artist_history(con, artist_name)
    if not history:
        raise ArtistNotFound(artist_name)

    heatmap_html, result, base_href = build_heatmap_html(
        history, f"artist_{artist_name}", request
    )

    filter_clear_html = ""
    if result:
        _, _, _, plays = result
        label = period_label(result)
        aggregated = aggregate_plays(plays)
        # Same card-grid layout as the unfiltered view below (not row()'s
        # plain-text list) - picking a period should narrow which tracks
        # show, not change how they're displayed. Cover art needs its own
        # lookup here since plays (unlike load_artist_tracks_page's query)
        # isn't pre-joined against album_images.
        album_by_name = {}
        for p in plays:
            if p.get("album"):
                album_by_name.setdefault(p["name"], p["album"])
        images = service.images_for_tracks(con, artist_name, set(album_by_name.values()))
        tracks_html = grid(
            "".join(
                card(
                    name,
                    f"/track/{quote(name)}?artist={quote(artist_name)}",
                    note=f"×{count}",
                    image_url=images.get(album_by_name.get(name)),
                )
                for name, _, count in aggregated
            ),
            compact=True,
        )
        filter_clear_html = filter_clear_link(label, base_href)
        play_count = len(plays)
    else:
        tracks_html = grid(_artist_tracks_html(con, artist_name, 0), compact=True)
        play_count = len(history)

    header = detail_header(
        f"<h1>{escape(artist_name)}</h1>",
        f"<p class='subtitle'>{play_count} play{'s' if play_count != 1 else ''}{filter_clear_html}</p>",
        hero_image(service.get_artist_image(con, artist_name)),
        heatmap_html,
    )
    return page(
        detail_layout(header, "Tracks", tracks_html, list_id="artist-tracks"),
        title=artist_name,
    )


@router.get(
    "/artist/{artist_name}/tracks",
    response_class=HTMLResponse,
    status_code=200,
    description="Infinite-scroll fragment: next batch of an artist's tracks",
)
def artist_tracks(artist_name: str, con: DBDep, offset: int = 0):
    return HTMLResponse(_artist_tracks_html(con, artist_name, offset))
