from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from src.database import DBDep

from . import service

router = APIRouter(tags=["previews"])


@router.get(
    "/preview",
    description="Redirects to a track's 30s Spotify preview clip, scraped from the "
    "public embed player (the official API's preview_url field is no longer "
    "populated for apps created after Nov 2024)",
)
def preview(track: str, artist: str, con: DBDep):
    track_id = service.resolve_track_id(con, track, artist)
    preview_url = service.fetch_preview_url(track_id) if track_id else None
    if not preview_url:
        raise HTTPException(status_code=404, detail="No preview available")
    return RedirectResponse(url=preview_url, status_code=302)
