import logging
from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from src.auth.service import require_auth
from src.database import DBDep
from src.html import button, page

from . import library_sync, service
from .exceptions import NotConnected

router = APIRouter(prefix="/scrobbler", tags=["scrobbler"], dependencies=[Depends(require_auth)])
logger = logging.getLogger("scrobbler")


def _status_content(con, sync_message: str | None = None) -> str:
    row = service.get_status(con)
    if row is None:
        return f"""
<h1>Scrobbler</h1>
<p class="subtitle">Not connected. Link your Spotify account to automatically pull in new
plays every couple of minutes, and keep playlists, liked songs, liked albums and followed
artists in sync, instead of manually re-uploading your export.</p>
{button("Connect Spotify", "/scrobbler/connect", hx_boost=False)}
"""
    last_poll = f"<li>Last checked: {escape(row['last_poll_at'])}</li>" if row["last_poll_at"] else ""
    new_count = (
        f"<li>New plays on last check: {row['last_poll_new']}</li>"
        if row["last_poll_new"] is not None
        else ""
    )
    error = (
        f"<p>Last error: {escape(row['last_error'])}</p>"
        if row["last_error"]
        else ""
    )
    message = f"<p class='subtitle'>{escape(sync_message)}</p>" if sync_message else ""
    return f"""
<h1>Scrobbler</h1>
<p class="subtitle">Connected since {escape(row['connected_at'])}.</p>
<ul>
  {last_poll}
  {new_count}
</ul>
{error}
{message}
<form action="/scrobbler/sync" method="post" style="display:inline">
  <button type="submit">Sync playlists now</button>
</form>
<form action="/scrobbler/disconnect" method="post" style="display:inline">
  <button type="submit">Disconnect</button>
</form>
"""


@router.get("", response_class=HTMLResponse, status_code=200, description="Scrobbler status page")
def status_page(con: DBDep, synced: str | None = None):
    return page(_status_content(con, synced), title="Scrobbler")


@router.get("/connect", status_code=302, description="Start Spotify OAuth login")
def connect():
    return RedirectResponse(url=service.start_authorization(), status_code=302)


@router.get(
    "/callback",
    response_class=HTMLResponse,
    status_code=200,
    description="Spotify OAuth callback: exchange code for tokens",
)
def callback(con: DBDep, code: str | None = None, state: str | None = None, error: str | None = None):
    if error:
        return page(f"<h1>Scrobbler</h1><p>{escape(error)}</p>", title="Scrobbler")
    if not code or not state or not service.verify_state(state):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    service.exchange_code(con, code)
    return RedirectResponse(url="/scrobbler", status_code=302)


@router.post(
    "/sync", status_code=302, description="Manually trigger a one-off library sync now"
)
def sync_now(con: DBDep):
    try:
        library_sync.ensure_migrations(con)
        counts = library_sync.sync_once(con)
        message = ", ".join(f"{k}: {v}" for k, v in counts.items()) or "Synced"
    except NotConnected:
        message = "Not connected"
    except Exception:
        logger.exception("manual library sync failed")
        message = "Sync failed - check server logs"
    return RedirectResponse(url=f"/scrobbler?synced={quote(message)}", status_code=302)


@router.post("/disconnect", status_code=302, description="Unlink the Spotify account")
def disconnect(con: DBDep):
    service.disconnect(con)
    return RedirectResponse(url="/scrobbler", status_code=302)
