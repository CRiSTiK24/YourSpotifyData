from html import escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from src.auth.service import require_auth
from src.database import DBDep
from src.html import page

from . import service

router = APIRouter(prefix="/scrobbler", tags=["scrobbler"], dependencies=[Depends(require_auth)])


def _status_content(con) -> str:
    row = service.get_status(con)
    if row is None:
        return """
<h1>Scrobbler</h1>
<p class="subtitle">Not connected. Link your Spotify account to automatically pull in new
plays every couple of minutes, instead of manually re-uploading your export.</p>
<a href="/scrobbler/connect" hx-boost="false" class="button-link">Connect Spotify</a>
"""
    last_poll = f"<li>Last checked: {escape(row['last_poll_at'])}</li>" if row["last_poll_at"] else ""
    new_count = (
        f"<li>New plays on last check: {row['last_poll_new']}</li>"
        if row["last_poll_new"] is not None
        else ""
    )
    error = (
        f"<p style='color:#f85149'>Last error: {escape(row['last_error'])}</p>"
        if row["last_error"]
        else ""
    )
    return f"""
<h1>Scrobbler</h1>
<p class="subtitle" style="color:#3fb950">Connected since {escape(row['connected_at'])}.</p>
<ul>
  {last_poll}
  {new_count}
</ul>
{error}
<form action="/scrobbler/disconnect" method="post">
  <button type="submit">Disconnect</button>
</form>
"""


@router.get("", response_class=HTMLResponse, status_code=200, description="Scrobbler status page")
def status_page(con: DBDep):
    return page(_status_content(con))


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
        return page(f"<h1>Scrobbler</h1><p style='color:#f85149'>{escape(error)}</p>")
    if not code or not state or not service.verify_state(state):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    service.exchange_code(con, code)
    return RedirectResponse(url="/scrobbler", status_code=302)


@router.post("/disconnect", status_code=302, description="Unlink the Spotify account")
def disconnect(con: DBDep):
    service.disconnect(con)
    return RedirectResponse(url="/scrobbler", status_code=302)
