from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse

from src.auth.service import require_write_access
from src.database import DBDep
from src.html import u
from src.users import service as users_service
from src.users.exceptions import UserValidationError

router = APIRouter(tags=["profile"], dependencies=[Depends(require_write_access)])


def profile_content_html(
    username: str, error: str | None = None, success: str | None = None
) -> str:
    message_html = ""
    if error:
        message_html = f"<p class='subtitle'>{escape(error)}</p>"
    elif success:
        message_html = f"<p class='subtitle'>{escape(success)}</p>"
    return f"""
<p class="subtitle">Change the username this account is served under
({escape(u(""))} is the base path for every page).</p>
{message_html}
<form class="search-form" action="{u("/profile")}" method="post">
  <input name="new_username" type="text" value="{escape(username)}" maxlength="64"
    aria-label="Username" required>
  <button type="submit" class="btn">Save</button>
</form>
"""


@router.get("/profile", status_code=302, description="Profile now lives on the account page")
def profile_redirect():
    return RedirectResponse(url=u("/account"), status_code=302)


@router.post(
    "/profile", status_code=302, description="Change this account's username (the /{username} slug)"
)
def profile_submit(
    con: DBDep, viewed_user: users_service.ViewedUserDep, new_username: str = Form(...)
):
    try:
        saved_username = users_service.set_username(con, viewed_user["id"], new_username)
    except UserValidationError as e:
        return RedirectResponse(
            url=u(f"/account?profile_error={quote(str(e))}#profile-section"), status_code=302
        )
    return RedirectResponse(
        url=f"/{saved_username}/account?profile_success="
        f"{quote(f'Username updated to {saved_username}.')}#profile-section",
        status_code=302,
    )
