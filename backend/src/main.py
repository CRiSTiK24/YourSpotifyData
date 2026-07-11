import os

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from src.albums.router import router as albums_router
from src.artists.router import router as artists_router
from src.exceptions import http_exception_handler
from src.home import router as home_router
from src.library.router import router as library_router
from src.playlists.router import router as playlists_router
from src.search.router import router as search_router
from src.tracks.router import router as tracks_router

_STATIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "static"
)

app = FastAPI(title="Your Spotify Data", version="1.0.0")

app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

app.include_router(home_router)
app.include_router(search_router)
app.include_router(library_router)
app.include_router(playlists_router)
app.include_router(artists_router)
app.include_router(albums_router)
app.include_router(tracks_router)

app.add_exception_handler(HTTPException, http_exception_handler)
