import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles

from src.albums.router import router as albums_router
from src.artists.router import router as artists_router
from src.auth import service as auth_service
from src.auth.exceptions import NotAuthenticated, not_authenticated_handler
from src.auth.router import router as auth_router
from src.covers.router import router as covers_router
from src.database import get_connection
from src.exceptions import http_exception_handler
from src.home import router as home_router
from src.html import logged_in_var
from src.images import service as images_service
from src.library.router import router as library_router
from src.palette import sync_css_palette
from src.playlists.router import router as playlists_router
from src.scrobbler import library_sync as library_sync_service
from src.scrobbler import service as scrobbler_service
from src.scrobbler.router import router as scrobbler_router
from src.search.router import router as search_router
from src.theme.router import router as theme_router
from src.tracks.router import router as tracks_router
from src.upload.router import router as upload_router

_STATIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "static"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    sync_css_palette()
    con = get_connection()
    try:
        library_sync_service.ensure_migrations(con)
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
        logged_in_var.set(auth_service.is_logged_in(request, con))
    finally:
        con.close()
    return await call_next(request)

app.include_router(home_router)
app.include_router(search_router)
app.include_router(library_router)
app.include_router(playlists_router)
app.include_router(artists_router)
app.include_router(albums_router)
app.include_router(tracks_router)
app.include_router(auth_router)
app.include_router(covers_router)
app.include_router(upload_router)
app.include_router(scrobbler_router)
app.include_router(theme_router)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(NotAuthenticated, not_authenticated_handler)
