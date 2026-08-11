from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

from src.database import DBDep
from src.html import page
from src.utils import parse_month_param

from .views import (
    liked_albums_content,
    most_listened_albums_rows_html,
    most_listened_combined_content,
    most_listened_rows_html,
)

router = APIRouter(tags=["library"])


@router.get(
    "/most-listened",
    response_class=HTMLResponse,
    status_code=200,
    description="Songs, albums and artists ranked by play count - Songs/Albums/Artists "
    "columns on desktop, tabs on mobile (see most_listened_combined_content)",
)
def most_listened(con: DBDep, start_month: str = "", end_month: str = ""):
    return page(
        most_listened_combined_content(
            con, parse_month_param(start_month), parse_month_param(end_month, end=True)
        ),
        title="Most Listened",
    )


@router.get(
    "/most-listened/more",
    response_class=HTMLResponse,
    status_code=200,
    description="Infinite-scroll fragment: next batch of most-listened rows",
)
def most_listened_more(
    con: DBDep, offset: int = 0, max_plays: int = 0, start_month: str = "", end_month: str = ""
):
    return HTMLResponse(
        most_listened_rows_html(
            con, offset, max_plays, parse_month_param(start_month), parse_month_param(end_month, end=True)
        )
    )


@router.get(
    "/most-listened-albums",
    status_code=302,
    description="Album browsing merged into /most-listened (Albums tab/column)",
)
def most_listened_albums_redirect():
    return RedirectResponse(url="/most-listened", status_code=302)


@router.get(
    "/most-listened-albums/more",
    response_class=HTMLResponse,
    status_code=200,
    description="Infinite-scroll fragment: next batch of most-listened-albums rows",
)
def most_listened_albums_more(
    con: DBDep, offset: int = 0, max_plays: int = 0, start_month: str = "", end_month: str = ""
):
    return HTMLResponse(
        most_listened_albums_rows_html(
            con, offset, max_plays, parse_month_param(start_month), parse_month_param(end_month, end=True)
        )
    )


@router.get(
    "/liked-albums", response_class=HTMLResponse, status_code=200, description="All liked albums"
)
def liked_albums(con: DBDep):
    return page(liked_albums_content(con), title="Albums I Like")
