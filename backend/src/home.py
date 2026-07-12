import sqlite3
from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from src.database import DBDep
from src.html import infinite_scroll_trigger, page, row, search_form
from src.search.service import search_track_history
from src.utils import aggregate_plays

router = APIRouter(tags=["home"])

QUICK_RESULTS_BATCH = 8

ABOUT_HTML = """
<p class="subtitle">At the moment this is a one-person thing which has already been done in
other projects. But what I'd like is that anyone can drop their Spotify export into a
browser, have it processed on the backend, and land in a real database alongside
everyone else's.</p>
<p class="subtitle">From one side there are many times where I've felt that it's very hard
to actually play with your own data, even this workaround to avoid using the API (because
it's been restricted to any new project) will take a few days of receiving the files, and
if you'd like to keep it synchronised you'd need to do something like LastFM who have
access to new streams. Also on the other side, I feel frustrated when I'm digging through
Spotify and there is no easy way to find other playlists that have X amount of songs in
common with me.</p>
<p class="subtitle">I saw some other projects doing some kind of fuzzy search based on the
title of the playlists or others, but tbh I think that we should be able to use that data
outside the platform, and do our own comparisons, recommendations and searches if the app
is not on par with our desires. Thus is what I hope to do with this repo, making a way to
not only see your own data, but to be able to also add your friend's or other music
enthusiasts' data and to be able to delve deep into whatever picks your curiosity, after
all music is such a beloved hobby for a reason.</p>
"""


def _quick_results_html(con: sqlite3.Connection, query: str, offset: int = 0) -> str:
    history = search_track_history(con, query)
    aggregated = aggregate_plays([{"name": r["name"], "singer": r["singer"]} for r in history])
    batch = aggregated[offset : offset + QUICK_RESULTS_BATCH]
    rows_html = "".join(
        row(
            name,
            f"/track/{quote(name)}?artist={quote(singer or '')}",
            singer,
            f"/artist/{quote(singer)}" if singer else None,
            note=f"×{count}",
        )
        for name, singer, count in batch
    )
    if not rows_html:
        return "<p class='info'>No matches.</p>" if offset == 0 else ""
    if offset + QUICK_RESULTS_BATCH < len(aggregated):
        next_href = f"/home/search/more?query={quote(query)}&offset={offset + QUICK_RESULTS_BATCH}"
        rows_html += infinite_scroll_trigger(next_href)
    return rows_html


def home_page() -> HTMLResponse:
    content = f"""
{
        search_form(
            "/home/search",
            "Search for a song or artist…",
            hx_target="#home-results",
            hx_select="#home-search-fragment",
            hx_swap="innerHTML",
            hx_push_url=False,
        )
    }
<hr class="divider">
<div id="home-results">{ABOUT_HTML}</div>
"""
    return page(content)


@router.get(
    "/", response_class=HTMLResponse, status_code=200, description="Home page"
)
def home():
    return home_page()


@router.get(
    "/home/search",
    response_class=HTMLResponse,
    status_code=200,
    description="Live quick-search fragment for the home page",
)
def home_search(con: DBDep, query: str = ""):
    query = query.strip()
    inner = ABOUT_HTML if not query else _quick_results_html(con, query)
    return HTMLResponse(f"<div id='home-search-fragment'>{inner}</div>")


@router.get(
    "/home/search/more",
    response_class=HTMLResponse,
    status_code=200,
    description="Infinite-scroll fragment: next batch of home quick-search results",
)
def home_search_more(con: DBDep, query: str = "", offset: int = 0):
    return HTMLResponse(_quick_results_html(con, query.strip(), offset))
