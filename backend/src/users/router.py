from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse

from src.auth.service import require_admin
from src.database import DBDep
from src.html import u

from . import service
from .exceptions import UserValidationError

router = APIRouter(tags=["users"], dependencies=[Depends(require_admin)])


def _users_table_html(con) -> str:
    rows = "".join(
        f"""
<tr>
  <td>{escape(usr["username"])}</td>
  <td>{escape(usr["email"])}</td>
  <td><span class="role-tag">{escape(usr["role"])}</span></td>
  <td>{
            ""
            if usr["role"] == "owner"
            else (
                f"<form action='{u('/admin/remove')}' method='post' hx-boost='false' "
                f"onsubmit=\"return confirm('Remove {usr['username']}? "
                "This revokes their login and disconnects their scrobbler right away "
                "(their already-imported history is kept).')\">"
                f"<input type='hidden' name='user_id' value='{usr['id']}'>"
                f"<button type='submit' class='btn'>Remove</button></form>"
            )
        }</td>
</tr>"""
        for usr in service.list_users(con)
    )
    return f"""
<div class="admin-users-wrap">
<table class="admin-users">
<thead><tr><th>Username</th><th>Email</th><th>Role</th><th></th></tr></thead>
<tbody>{rows}</tbody>
</table>
</div>"""


def _add_member_form_html() -> str:
    return f"""
<h3>Add member</h3>
<form class="search-form" action="{u("/admin/add")}" method="post">
  <input name="new_username" type="text" placeholder="username" aria-label="Username" maxlength="64" required>
  <input name="email" type="email" placeholder="you@example.com" aria-label="Email" required>
  <button type="submit" class="btn">Add</button>
</form>
"""


def admin_content(con, error: str | None = None, success: str | None = None) -> str:
    message_html = ""
    if error:
        message_html = f"<p class='subtitle'>{escape(error)}</p>"
    elif success:
        message_html = f"<p class='subtitle'>{escape(success)}</p>"
    count = len(service.list_users(con))
    at_capacity = count >= service.MAX_USERS
    add_form_html = (
        f"<h3>Add member</h3><p class='subtitle'>At the {service.MAX_USERS}-account limit — "
        "remove someone before adding another.</p>"
        if at_capacity
        else _add_member_form_html()
    )
    return f"""
<p class="subtitle">Up to {service.MAX_USERS} accounts total ({count}/{service.MAX_USERS} used).
Removing an account revokes their login and disconnects their scrobbler, but keeps their
already-imported listening history intact.</p>
{message_html}
{_users_table_html(con)}
{add_form_html}
"""


@router.get("/admin", status_code=302, description="Admin now lives on the account page")
def admin_redirect():
    return RedirectResponse(url=u("/account"), status_code=302)


@router.post("/admin/add", status_code=302, description="Add a member account")
def admin_add(con: DBDep, new_username: str = Form(...), email: str = Form(...)):
    try:
        member = service.add_member(con, new_username, email)
    except UserValidationError as e:
        return RedirectResponse(
            url=u(f"/account?admin_error={quote(str(e))}#admin-section"), status_code=302
        )
    return RedirectResponse(
        url=u(f"/account?admin_success={quote(f'Added {member["username"]}.')}#admin-section"),
        status_code=302,
    )


@router.post("/admin/remove", status_code=302, description="Remove a member account")
def admin_remove(con: DBDep, user_id: int = Form(...)):
    try:
        service.remove_member(con, user_id)
    except UserValidationError as e:
        return RedirectResponse(
            url=u(f"/account?admin_error={quote(str(e))}#admin-section"), status_code=302
        )
    return RedirectResponse(
        url=u(f"/account?admin_success={quote('Account removed.')}#admin-section"),
        status_code=302,
    )
