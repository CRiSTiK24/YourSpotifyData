import os
import tempfile
from html import escape

from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from src.auth.service import require_write_access
from src.database import DBDep
from src.html import page, u
from src.users import service as users_service

from . import service
from .exceptions import JobNotFound

router = APIRouter(tags=["upload"], dependencies=[Depends(require_write_access)])


def upload_form_html() -> str:
    return f"""
<p class="subtitle">Drop your GDPR export zip. Only data newer than what's
already imported gets added — safe to re-upload the same or a newer export.</p>
<form action="{u("/upload")}" method="post" enctype="multipart/form-data">
  <div class="file-drop">
    <input type="file" name="file" accept=".zip" required>
  </div>
  <button type="submit" class="btn">Upload</button>
</form>
"""


@router.get("/upload", status_code=302, description="Upload now lives on the account page")
def upload_redirect():
    return RedirectResponse(url=u("/account"), status_code=302)


@router.post("/upload", status_code=200, description="Accept a zip and start processing")
async def upload_submit(
    background_tasks: BackgroundTasks,
    con: DBDep,
    viewed_user: users_service.ViewedUserDep,
    file: UploadFile,
):
    fd, tmp_path = tempfile.mkstemp(suffix=".zip")
    size = 0
    with os.fdopen(fd, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > service.MAX_ZIP_SIZE_COMPRESSED:
                os.remove(tmp_path)
                return page(
                    "<h1>Upload failed</h1>"
                    f"<p class='subtitle'>File too large "
                    f"(max {service.MAX_ZIP_SIZE_COMPRESSED // (1024 * 1024)}MB).</p>",
                    title="Upload",
                )
            f.write(chunk)

    job_id = service.create_job(con, viewed_user["id"])
    background_tasks.add_task(service.process_upload, job_id, tmp_path, viewed_user["id"])
    return RedirectResponse(url=u(f"/upload/{job_id}"), status_code=303)


def _status_block(job) -> str:
    status = job["status"]
    if status in ("done", "error"):
        poll_attrs = ""
    else:
        poll_attrs = (
            f" hx-get='{u(f'/upload/{job["id"]}/status')}' hx-trigger='every 2s' hx-target='this' "
            f"hx-select='unset' hx-swap='outerHTML'"
        )

    if status == "done":
        body = f"""
<p>Done.</p>
<ul>
  <li>{job["new_history_rows"] or 0} new plays</li>
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
def upload_status(job_id: int, con: DBDep, viewed_user: users_service.ViewedUserDep):
    job = service.get_job(con, job_id, viewed_user["id"])
    if job is None:
        raise JobNotFound(job_id)
    content = f"""
<h1>Import #{job["id"]}</h1>
{_status_block(job)}
"""
    return page(content, title=f"Import #{job['id']}")


@router.get(
    "/upload/{job_id}/status",
    response_class=HTMLResponse,
    status_code=200,
    description="Polled job status fragment",
)
def upload_status_fragment(job_id: int, con: DBDep, viewed_user: users_service.ViewedUserDep):
    job = service.get_job(con, job_id, viewed_user["id"])
    if job is None:
        raise JobNotFound(job_id)
    return HTMLResponse(_status_block(job))
