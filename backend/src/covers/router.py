import logging
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from src.duotone import recolor_image, resize_image
from src.palette import Palette

router = APIRouter(tags=["covers"])
logger = logging.getLogger("covers")

_ALLOWED_EXACT_SPOTIFY_CDN_HOSTS = {"i.scdn.co", "mosaic.scdn.co"}
_ALLOWED_SPOTIFY_CDN_HOST_SUFFIX = ".spotifycdn.com"

_PALETTE_HEX = [c.value for c in Palette]

_MIN_SIZE = 16
_MAX_SIZE = 800


def _is_allowed_spotify_cdn_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    return hostname in _ALLOWED_EXACT_SPOTIFY_CDN_HOSTS or hostname.endswith(
        _ALLOWED_SPOTIFY_CDN_HOST_SUFFIX
    )


@lru_cache(maxsize=1024)
def _fetch_recolored(src: str, size: int | None) -> bytes:
    with urllib.request.urlopen(src, timeout=10) as resp:
        original = resp.read()
    return recolor_image(original, _PALETTE_HEX, size)


@lru_cache(maxsize=1024)
def _fetch_original_colors(src: str, size: int | None) -> bytes:
    with urllib.request.urlopen(src, timeout=10) as resp:
        original = resp.read()
    return resize_image(original, size)


@router.get("/cover", description="Proxies a Spotify cover image, recolored into the site palette")
def cover(
    src: str,
    size: int | None = Query(default=None, ge=_MIN_SIZE, le=_MAX_SIZE),
    raw: bool = Query(
        default=False, description="Skip the site-palette recolor, keep original colors"
    ),
):
    parsed = urllib.parse.urlparse(src)
    if parsed.scheme != "https" or not _is_allowed_spotify_cdn_host(parsed.hostname):
        raise HTTPException(status_code=400, detail="Unsupported image source")
    try:
        processed = _fetch_original_colors(src, size) if raw else _fetch_recolored(src, size)
    except urllib.error.URLError:
        raise HTTPException(status_code=502, detail="Failed to fetch source image") from None
    except Exception:
        logger.exception("failed recoloring %s", src)
        raise HTTPException(status_code=500, detail="Failed to process image") from None
    return Response(
        content=processed,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )
