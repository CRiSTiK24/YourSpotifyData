import logging
from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from src.auth.service import require_write_access
from src.database import DBDep
from src.html import button, page, u
from src.users import service as users_service
from src.utils import relative_time

from . import library_sync, service
from .exceptions import NotConnected

router = APIRouter(
    prefix="/scrobbler", tags=["scrobbler"], dependencies=[Depends(require_write_access)]
)
logger = logging.getLogger("scrobbler")


def status_content(con, user_id: int, sync_message: str | None = None) -> str:
    row = service.get_status(con, user_id)
    if row is None:
        return f"""
<span class="status-badge">Not connected</span>
<p class="subtitle">Link your Spotify account to automatically pull in new
plays every couple of minutes, and keep playlists, liked songs, liked albums and followed
artists in sync, instead of manually re-uploading your export.</p>
<div class="account-actions">{button("Connect Spotify", u("/scrobbler/connect"), hx_boost=False)}</div>
"""
    last_poll = (
        f"<li><span class='label'>Last checked</span>"
        f"<span title='{escape(row['last_poll_at'])}'>{relative_time(row['last_poll_at'])}</span></li>"
        if row["last_poll_at"]
        else ""
    )
    new_count = (
        f"<li><span class='label'>New plays on last check</span><span>{row['last_poll_new']}</span></li>"
        if row["last_poll_new"] is not None
        else ""
    )
    error = (
        f"<p class='subtitle'>Last error: {escape(row['last_error'])}</p>"
        if row["last_error"]
        else ""
    )
    message = f"<p class='subtitle'>{escape(sync_message)}</p>" if sync_message else ""
    return f"""
<span class="status-badge connected" title="{escape(row["connected_at"])}">Connected {relative_time(row["connected_at"])}</span>
<ul class="account-stat-list">
  {last_poll}
  {new_count}
</ul>
{error}
{message}
<div class="account-actions">
  <form action="{u("/scrobbler/sync")}" method="post">
    <button type="submit" class="btn">Sync playlists now</button>
  </form>
  <form action="{u("/scrobbler/disconnect")}" method="post" hx-boost="false"
    onsubmit="return confirm('Disconnect Spotify? You can reconnect any time, but the background sync stops until then.')">
    <button type="submit" class="btn">Disconnect</button>
  </form>
</div>
"""


@router.get("", status_code=302, description="Scrobbler now lives on the account page")
def status_redirect():
    return RedirectResponse(url=u("/account"), status_code=302)


@router.get("/connect", status_code=302, description="Start Spotify OAuth login")
def connect(con: DBDep, viewed_user: users_service.ViewedUserDep):
    return RedirectResponse(
        url=service.start_authorization(con, viewed_user["id"]), status_code=302
    )


@router.get(
    "/callback",
    response_class=HTMLResponse,
    status_code=200,
    description="Spotify OAuth callback: exchange code for tokens",
)
def callback(
    con: DBDep, code: str | None = None, state: str | None = None, error: str | None = None
):
    if error:
        return page(f"<h1>Scrobbler</h1><p>{escape(error)}</p>", title="Scrobbler")
    user_id = service.resolve_state(state) if state else None
    if not code or user_id is None:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    service.exchange_code(con, user_id, code)
    return RedirectResponse(url=u("/account#scrobbler-section"), status_code=302)


@router.post("/sync", status_code=302, description="Manually trigger a one-off library sync now")
def sync_now(con: DBDep, viewed_user: users_service.ViewedUserDep):
    try:
        library_sync.ensure_migrations(con)
        counts = library_sync.sync_once(con, viewed_user["id"])
        message = ", ".join(f"{k}: {v}" for k, v in counts.items()) or "Synced"
    except NotConnected:
        message = "Not connected"
    except Exception:
        logger.exception("manual library sync failed")
        message = "Sync failed - check server logs"
    return RedirectResponse(
        url=u(f"/account?synced={quote(message)}#scrobbler-section"), status_code=302
    )


@router.post("/disconnect", status_code=302, description="Unlink the Spotify account")
def disconnect(con: DBDep, viewed_user: users_service.ViewedUserDep):
    service.disconnect(con, viewed_user["id"])
    return RedirectResponse(url=u("/account#scrobbler-section"), status_code=302)
