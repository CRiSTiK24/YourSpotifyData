import logging
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from src.duotone import recolor_image
from src.palette import Palette

router = APIRouter(tags=["covers"])
logger = logging.getLogger("covers")

# Spotify's CDN hosts for cover art: i.scdn.co for uploaded/custom artwork,
# mosaic.scdn.co for Spotify's auto-generated 4-album-collage playlist
# covers, and *.spotifycdn.com for regional/edge variants (e.g.
# image-cdn-fa.spotifycdn.com, image-cdn-ak.spotifycdn.com - Spotify serves
# these per-region and the exact subdomain isn't documented/stable, so the
# whole spotifycdn.com domain is allowed rather than enumerating suffixes
# one at a time). Restricting to these hosts (not open to any URL) prevents
# /cover from being used as an SSRF relay via an attacker-supplied src=.
_ALLOWED_EXACT_HOSTS = {"i.scdn.co", "mosaic.scdn.co"}
_ALLOWED_HOST_SUFFIX = ".spotifycdn.com"

_PALETTE_HEX = [c.value for c in Palette]

# Bounds on the requested size= param - keeps a caller from forcing an
# unbounded PIL resize (memory/CPU) via an arbitrary query value.
_MIN_SIZE = 16
_MAX_SIZE = 800


def _is_allowed_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    return hostname in _ALLOWED_EXACT_HOSTS or hostname.endswith(_ALLOWED_HOST_SUFFIX)


@lru_cache(maxsize=1024)
def _recolored(src: str, size: int | None) -> bytes:
    """Fetch + recolor is deterministic for a given (url, size) pair, so
    caching in memory avoids redoing the work on every page view of the
    same cover - the image itself is still generated fresh per unique
    src/size, not precomputed/stored ahead of time."""
    with urllib.request.urlopen(src, timeout=10) as resp:
        original = resp.read()
    return recolor_image(original, _PALETTE_HEX, size)


@router.get("/cover", description="Proxies a Spotify cover image, recolored into the site palette")
def cover(src: str, size: int | None = Query(default=None, ge=_MIN_SIZE, le=_MAX_SIZE)):
    parsed = urllib.parse.urlparse(src)
    if parsed.scheme != "https" or not _is_allowed_host(parsed.hostname):
        raise HTTPException(status_code=400, detail="Unsupported image source")
    try:
        processed = _recolored(src, size)
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
