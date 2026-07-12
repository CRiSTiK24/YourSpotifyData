from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from src.database import DBDep
from src.html import page

from .views import liked_albums_content, liked_songs_content

router = APIRouter(tags=["library"])


@router.get(
    "/liked-songs", response_class=HTMLResponse, status_code=200, description="All liked songs"
)
def liked_songs(con: DBDep):
    return page(liked_songs_content(con))


@router.get(
    "/liked-albums", response_class=HTMLResponse, status_code=200, description="All liked albums"
)
def liked_albums(con: DBDep):
    return page(liked_albums_content(con))
