from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.database import DBDep
from src.heatmap import build_heatmap_html, resolve_period_filter
from src.html import card, detail_header, detail_layout, grid, hero_image, page, paginated_fragment
from src.utils import aggregate_plays, parse_month_param, pluralize

from . import service
from .exceptions import ArtistNotFound
from .views import most_listened_artists_rows_html

router = APIRouter(tags=["artists"])

ARTIST_TRACKS_BATCH = 20


def _artist_tracks_cards_fragment(con, artist_name: str, offset: int) -> str:
    tracks = service.load_artist_tracks_page(con, artist_name, offset, ARTIST_TRACKS_BATCH)
    has_more = len(tracks) > ARTIST_TRACKS_BATCH
    tracks = tracks[:ARTIST_TRACKS_BATCH]
    cards_html = "".join(
        card(
            t["name"],
            f"/track/{quote(t['name'])}?artist={quote(artist_name)}",
            note=str(t["cnt"]),
            image_url=t["image_url"],
            preview_artist=artist_name,
        )
        for t in tracks
    )
    return paginated_fragment(
        cards_html,
        offset=offset,
        has_more=has_more,
        next_href=f"/artist/{quote(artist_name)}/tracks?offset={offset + ARTIST_TRACKS_BATCH}",
    )


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
    con: DBDep,
    offset: int = 0,
    max_plays: int = 0,
    start_month: str = "",
    end_month: str = "",
    genre: str = "",
):
    return HTMLResponse(
        most_listened_artists_rows_html(
            con,
            offset,
            max_plays,
            parse_month_param(start_month),
            parse_month_param(end_month, end=True),
            genre,
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

    heatmap_html, result, base_href = build_heatmap_html(history, f"artist_{artist_name}", request)

    plays, play_count, filter_clear_html = resolve_period_filter(history, result, base_href)
    if result:
        aggregated = aggregate_plays(plays)
        album_by_name = {}
        for p in plays:
            if p.get("album"):
                album_by_name.setdefault(p["name"], p["album"])
        images = service.album_image_urls_by_name(con, artist_name, set(album_by_name.values()))
        tracks_html = grid(
            "".join(
                card(
                    name,
                    f"/track/{quote(name)}?artist={quote(artist_name)}",
                    note=str(count),
                    image_url=images.get(album_by_name.get(name)),
                    preview_artist=artist_name,
                )
                for name, _, count in aggregated
            ),
            compact=True,
        )
    else:
        tracks_html = grid(_artist_tracks_cards_fragment(con, artist_name, 0), compact=True)

    header = detail_header(
        f"<h1>{escape(artist_name)}</h1>",
        f"<p class='subtitle'>{pluralize(play_count, 'play')}{filter_clear_html}</p>",
        hero_image(service.get_artist_image(con, artist_name), large=True),
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
    return HTMLResponse(_artist_tracks_cards_fragment(con, artist_name, offset))
