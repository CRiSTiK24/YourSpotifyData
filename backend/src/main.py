import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from src import app_settings
from src.account.router import router as account_router
from src.albums.router import router as albums_router
from src.artists.router import router as artists_router
from src.auth import service as auth_service
from src.auth.exceptions import NotAuthenticated, not_authenticated_handler
from src.auth.router import router as auth_router
from src.covers.router import router as covers_router
from src.database import ensure_base_schema, get_connection
from src.exceptions import http_exception_handler
from src.home import router as home_router
from src.html import (
    AGGREGATE_ROOT_SEGMENTS,
    available_usernames_var,
    can_write_var,
    current_username,
    is_owner_home_var,
    logged_in_var,
)
from src.images import service as images_service
from src.library import play_counts as library_play_counts
from src.library.router import router as library_router
from src.palette import sync_css_palette
from src.playlists.router import listing_router as playlists_listing_router
from src.playlists.router import router as playlists_router
from src.previews.router import router as previews_router
from src.profile.router import router as profile_router
from src.scrobbler import library_sync as library_sync_service
from src.scrobbler import service as scrobbler_service
from src.scrobbler.router import router as scrobbler_router
from src.search import service as search_service
from src.search.router import router as search_router
from src.setup import service as setup_service
from src.setup.router import router as setup_router
from src.theme.router import router as theme_router
from src.tracks.router import router as tracks_router
from src.upload.router import router as upload_router
from src.users import service as users_service
from src.users.router import router as users_router

_STATIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "static"
)

logger = logging.getLogger("setup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    sync_css_palette()
    con = get_connection()
    try:
        ensure_base_schema(con)
        users_service.ensure_schema(con)
        app_settings.ensure_schema(con)
        library_sync_service.ensure_migrations(con)
        images_service.ensure_schema_columns(con)
        search_service.ensure_track_history_fts_covers_album(con)
        library_play_counts.ensure_monthly_play_count_tables(con)
        scrobbler_service.ensure_user_scoped_schema(con)
        if users_service.get_owner(con) is None:
            token = setup_service.get_or_create_setup_token()
            logger.warning(
                "No owner account yet - visit /setup and enter this token to finish setup: %s",
                token,
            )
    finally:
        con.close()
    poll_task = asyncio.create_task(scrobbler_service.poll_loop())
    library_sync_task = asyncio.create_task(library_sync_service.sync_loop())
    image_task = asyncio.create_task(images_service.image_fetch_loop())
    yield
    poll_task.cancel()
    library_sync_task.cancel()
    image_task.cancel()


app = FastAPI(title="Your Spotify Data", version="1.0.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.middleware("http")
async def auth_state_middleware(request: Request, call_next):
    con = get_connection()
    try:
        owner = users_service.get_owner(con)
        if owner is None:
            path = request.url.path
            if not (path == "/setup" or path.startswith("/static/")):
                return RedirectResponse(url="/setup", status_code=302)
            return await call_next(request)
        first_segment = request.url.path.strip("/").split("/", 1)[0]
        viewed_user = users_service.get_by_username(con, first_segment)
        is_aggregate = viewed_user is None and first_segment in AGGREGATE_ROOT_SEGMENTS
        page_username = viewed_user["username"] if viewed_user else owner["username"]
        current_username.set("" if is_aggregate else page_username)
        available_usernames_var.set([u["username"] for u in users_service.list_users(con)])

        current_user = None
        try:
            current_user = auth_service.get_current_user(request, con)
        except NotAuthenticated:
            pass

        logged_in_var.set(current_user is not None)
        can_write_var.set(
            not is_aggregate
            and current_user is not None
            and (current_user["role"] == "owner" or current_user["username"] == page_username)
        )
        is_owner_home_var.set(
            not is_aggregate
            and current_user is not None
            and current_user["role"] == "owner"
            and current_user["username"] == page_username
        )
    finally:
        con.close()
    return await call_next(request)


user_router = APIRouter(
    prefix="/{username}", dependencies=[Depends(users_service.resolve_viewed_user)]
)
user_router.include_router(account_router)
user_router.include_router(home_router)
user_router.include_router(search_router)
user_router.include_router(library_router)
user_router.include_router(playlists_listing_router)
user_router.include_router(playlists_router)
user_router.include_router(artists_router)
user_router.include_router(albums_router)
user_router.include_router(tracks_router)
user_router.include_router(upload_router)
user_router.include_router(scrobbler_router)
user_router.include_router(theme_router)
user_router.include_router(profile_router)
user_router.include_router(users_router)

app.include_router(user_router)

# Same read-only routers as above, mounted a second time with no
# "/{username}" prefix - resolve_viewed_user (src/users/service.py) returns
# None here since there's no username path param, which every in-scope
# route/service function treats as "no filter, merge across every user"
# rather than one person's data.
app.include_router(home_router)
app.include_router(search_router)
app.include_router(library_router)
app.include_router(playlists_listing_router)
app.include_router(artists_router)
app.include_router(albums_router)
app.include_router(tracks_router)
app.include_router(theme_router)

app.include_router(auth_router)
app.include_router(covers_router)
app.include_router(previews_router)
app.include_router(setup_router)


@app.get("/")
def root_redirect():
    return RedirectResponse(url="/now", status_code=302)


app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(NotAuthenticated, not_authenticated_handler)
