import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from src.albums.router import router as albums_router
from src.artists.router import router as artists_router
from src.auth.exceptions import NotAuthenticated, not_authenticated_handler
from src.auth.router import router as auth_router
from src.exceptions import http_exception_handler
from src.home import router as home_router
from src.images import service as images_service
from src.library.router import router as library_router
from src.playlists.router import router as playlists_router
from src.scrobbler import service as scrobbler_service
from src.scrobbler.router import router as scrobbler_router
from src.search.router import router as search_router
from src.tracks.router import router as tracks_router
from src.upload.router import router as upload_router

_STATIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "static"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    poll_task = asyncio.create_task(scrobbler_service.poll_loop())
    image_task = asyncio.create_task(images_service.image_fetch_loop())
    yield
    poll_task.cancel()
    image_task.cancel()


app = FastAPI(title="Your Spotify Data", version="1.0.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

app.include_router(home_router)
app.include_router(search_router)
app.include_router(library_router)
app.include_router(playlists_router)
app.include_router(artists_router)
app.include_router(albums_router)
app.include_router(tracks_router)
app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(scrobbler_router)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(NotAuthenticated, not_authenticated_handler)
