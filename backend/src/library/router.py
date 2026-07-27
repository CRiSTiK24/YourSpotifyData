from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from src.database import DBDep
from src.html import page

from .views import (
    liked_albums_content,
    most_listened_albums_content,
    most_listened_albums_rows_html,
    most_listened_content,
    most_listened_rows_html,
)

router = APIRouter(tags=["library"])


@router.get(
    "/most-listened",
    response_class=HTMLResponse,
    status_code=200,
    description="Every played track ranked by play count",
)
def most_listened(con: DBDep, start_year: int = 0, end_year: int = 0):
    return page(most_listened_content(con, start_year, end_year))


@router.get(
    "/most-listened/more",
    response_class=HTMLResponse,
    status_code=200,
    description="Infinite-scroll fragment: next batch of most-listened rows",
)
def most_listened_more(
    con: DBDep, offset: int = 0, max_plays: int = 0, start_year: int = 0, end_year: int = 0
):
    return HTMLResponse(most_listened_rows_html(con, offset, max_plays, start_year, end_year))


@router.get(
    "/most-listened-albums",
    response_class=HTMLResponse,
    status_code=200,
    description="Every played album ranked by play count",
)
def most_listened_albums(con: DBDep, start_year: int = 0, end_year: int = 0):
    return page(most_listened_albums_content(con, start_year, end_year))


@router.get(
    "/most-listened-albums/more",
    response_class=HTMLResponse,
    status_code=200,
    description="Infinite-scroll fragment: next batch of most-listened-albums rows",
)
def most_listened_albums_more(
    con: DBDep, offset: int = 0, max_plays: int = 0, start_year: int = 0, end_year: int = 0
):
    return HTMLResponse(
        most_listened_albums_rows_html(con, offset, max_plays, start_year, end_year)
    )


@router.get(
    "/liked-albums", response_class=HTMLResponse, status_code=200, description="All liked albums"
)
def liked_albums(con: DBDep):
    return page(liked_albums_content(con))
