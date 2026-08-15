from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.database import DBDep
from src.html import page, u
from src.users import service as users_service
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
def most_listened(
    request: Request,
    con: DBDep,
    viewed_user: users_service.ViewedUserDep,
    start_month: str = "",
    end_month: str = "",
    genre: str = "",
):
    # the genre carousel's own hx-get (hx-target='#ml-results') marks its
    # tags hx-swap-oob so a click patches them in place without resetting
    # the carousel's scroll position (see word_cloud()'s oob param) - but
    # any other htmx-driven request to this same route (hx-boost nav from
    # the hamburger menu, a homepage genre link, etc.) also has htmx
    # extract-and-discard that oob element on arrival, since there's no
    # existing #ml-genre-tags in the DOM yet to patch into - which would
    # otherwise delete it from the response before the real page's own
    # #content swap ever inserts it, rendering the carousel empty until a
    # real (non-htmx) reload. Only setting oob=True when HX-Target
    # confirms this request is that specific carousel-click case avoids
    # stripping it out everywhere else.
    is_genre_swap = request.headers.get("hx-target") == "ml-results"
    user_id = viewed_user["id"] if viewed_user else None
    return page(
        most_listened_combined_content(
            con,
            user_id,
            parse_month_param(start_month),
            parse_month_param(end_month, end=True),
            genre,
            oob=is_genre_swap,
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
    con: DBDep,
    viewed_user: users_service.ViewedUserDep,
    offset: int = 0,
    max_plays: int = 0,
    start_month: str = "",
    end_month: str = "",
    genre: str = "",
):
    user_id = viewed_user["id"] if viewed_user else None
    return HTMLResponse(
        most_listened_rows_html(
            con,
            user_id,
            offset,
            max_plays,
            parse_month_param(start_month),
            parse_month_param(end_month, end=True),
            genre,
        )
    )


@router.get(
    "/most-listened-albums",
    status_code=302,
    description="Album browsing merged into /most-listened (Albums tab/column)",
)
def most_listened_albums_redirect():
    return RedirectResponse(url=u("/most-listened"), status_code=302)


@router.get(
    "/most-listened-albums/more",
    response_class=HTMLResponse,
    status_code=200,
    description="Infinite-scroll fragment: next batch of most-listened-albums rows",
)
def most_listened_albums_more(
    con: DBDep,
    viewed_user: users_service.ViewedUserDep,
    offset: int = 0,
    max_plays: int = 0,
    start_month: str = "",
    end_month: str = "",
    genre: str = "",
):
    user_id = viewed_user["id"] if viewed_user else None
    return HTMLResponse(
        most_listened_albums_rows_html(
            con,
            user_id,
            offset,
            max_plays,
            parse_month_param(start_month),
            parse_month_param(end_month, end=True),
            genre,
        )
    )


@router.get(
    "/liked-albums", response_class=HTMLResponse, status_code=200, description="All liked albums"
)
def liked_albums(con: DBDep, viewed_user: users_service.ViewedUserDep):
    user_id = viewed_user["id"] if viewed_user else None
    return page(liked_albums_content(con, user_id), title="Albums I Like")
