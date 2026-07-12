import os
import tempfile
from html import escape

from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from src.auth.service import require_auth
from src.database import DBDep
from src.html import page

from . import service
from .exceptions import JobNotFound

router = APIRouter(tags=["upload"], dependencies=[Depends(require_auth)])


@router.get(
    "/upload",
    response_class=HTMLResponse,
    status_code=200,
    description="Upload a Spotify export zip",
)
def upload_form():
    content = """
<h1>Upload Spotify export</h1>
<p class="subtitle">Drop your GDPR export zip. Only data newer than what's
already imported gets added — safe to re-upload the same or a newer export.</p>
<form action="/upload" method="post" enctype="multipart/form-data">
  <input type="file" name="file" accept=".zip" required>
  <button type="submit">Upload</button>
</form>
"""
    return page(content)


@router.post("/upload", status_code=200, description="Accept a zip and start processing")
async def upload_submit(background_tasks: BackgroundTasks, con: DBDep, file: UploadFile):
    fd, tmp_path = tempfile.mkstemp(suffix=".zip")
    size = 0
    with os.fdopen(fd, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > service.MAX_ZIP_SIZE:
                os.remove(tmp_path)
                return page(
                    "<h1>Upload failed</h1>"
                    f"<p class='subtitle'>File too large "
                    f"(max {service.MAX_ZIP_SIZE // (1024 * 1024)}MB).</p>"
                )
            f.write(chunk)

    job_id = service.create_job(con)
    background_tasks.add_task(service.process_upload, job_id, tmp_path)
    return RedirectResponse(url=f"/upload/{job_id}", status_code=303)


def _status_block(job) -> str:
    status = job["status"]
    if status in ("done", "error"):
        poll_attrs = ""
    else:
        # hx-target/hx-select pinned to itself and unset — without this it
        # inherits hx-target="#content" / hx-select="#content" from <body>,
        # and since this polled fragment has no #content element, that
        # inherited select-and-swap wipes the entire page content out on
        # the very first poll (same failure mode as infinite_scroll_trigger).
        poll_attrs = (
            f" hx-get='/upload/{job['id']}/status' hx-trigger='every 2s' hx-target='this' "
            f"hx-select='unset' hx-swap='outerHTML'"
        )

    if status == "done":
        body = f"""
<p>Done.</p>
<ul>
  <li>{job['new_history_rows'] or 0} new plays</li>
  <li>{job['new_library_tracks'] or 0} new liked tracks</li>
  <li>{job['new_library_albums'] or 0} new liked albums</li>
  <li>{job['new_library_artists'] or 0} new liked artists</li>
  <li>{job['new_playlists'] or 0} new playlists</li>
  <li>{job['new_playlist_tracks'] or 0} new playlist tracks</li>
</ul>
"""
    elif status == "error":
        body = f"<p>Failed: {escape(job['message'] or 'unknown error')}</p>"
    else:
        body = f"<p>Status: {escape(status)}…</p>"

    return f"<div id='job-status'{poll_attrs}>{body}</div>"


@router.get(
    "/upload/{job_id}",
    response_class=HTMLResponse,
    status_code=200,
    description="Import job status page",
)
def upload_status(job_id: int, con: DBDep):
    job = service.get_job(con, job_id)
    if job is None:
        raise JobNotFound(job_id)
    content = f"""
<h1>Import #{job['id']}</h1>
{_status_block(job)}
"""
    return page(content)


@router.get(
    "/upload/{job_id}/status",
    response_class=HTMLResponse,
    status_code=200,
    description="Polled job status fragment",
)
def upload_status_fragment(job_id: int, con: DBDep):
    job = service.get_job(con, job_id)
    if job is None:
        raise JobNotFound(job_id)
    return HTMLResponse(_status_block(job))
