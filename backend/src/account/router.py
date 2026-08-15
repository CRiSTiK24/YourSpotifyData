from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from src.auth.service import require_write_access
from src.database import DBDep
from src.html import is_owner_home_var, page, page_header, widget
from src.profile.router import profile_content_html
from src.scrobbler.router import status_content as scrobbler_content_html
from src.upload.router import upload_form_html
from src.users import service as users_service
from src.users.router import admin_content

router = APIRouter(tags=["account"], dependencies=[Depends(require_write_access)])


@router.get(
    "/account",
    response_class=HTMLResponse,
    status_code=200,
    description="Unified account settings: upload, scrobbler, profile, and (owner-only) admin",
)
def account_hub(
    con: DBDep,
    viewed_user: users_service.ViewedUserDep,
    synced: str = "",
    profile_error: str = "",
    profile_success: str = "",
    admin_error: str = "",
    admin_success: str = "",
):
    sections = [
        widget("Upload", upload_form_html(), id="upload-section"),
        widget(
            "Scrobbler",
            scrobbler_content_html(con, viewed_user["id"], synced or None),
            id="scrobbler-section",
        ),
        widget(
            "Profile",
            profile_content_html(
                viewed_user["username"], profile_error or None, profile_success or None
            ),
            id="profile-section",
        ),
    ]
    if is_owner_home_var.get():
        sections.append(
            widget(
                "Admin",
                admin_content(con, admin_error or None, admin_success or None),
                id="admin-section",
            )
        )

    content = page_header("Account") + f"<div class='account-sections'>{''.join(sections)}</div>"
    return page(content, title="Account")
