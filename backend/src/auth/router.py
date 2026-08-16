from html import escape

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.database import DBDep
from src.html import page
from src.users import service as users_service

from . import service

router = APIRouter(tags=["auth"])


def _code_form(email: str) -> str:
    return f"""
<h1>Enter your code</h1>
<p class="subtitle">Check your email for a 6-digit code (expires in 5 minutes).</p>
<form class="search-form" action="/login/verify" method="post">
  <input type="hidden" name="email" value="{escape(email)}">
  <input name="code" type="text" inputmode="numeric" maxlength="6" placeholder="123456"
    aria-label="6-digit login code" autofocus>
  <button type="submit">Verify</button>
</form>
"""


@router.get("/login", response_class=HTMLResponse, status_code=200, description="Login form")
def login_form():
    content = f"""
<h1>Login</h1>
<form class="search-form" action="/login" method="post">
  <input name="email" type="email" placeholder="you@example.com" aria-label="Email address" autofocus required>
  <button type="submit">Send code</button>
</form>
<p class="subtitle">This instance is limited to {users_service.MAX_USERS} accounts. If you don't
have one yet, contact whoever hosts this instance to get an account with music access set up
for you.</p>
"""
    return page(content, title="Login")


@router.post(
    "/login", response_class=HTMLResponse, status_code=200, description="Request a login code"
)
def login_submit(con: DBDep, email: str = Form(...)):
    service.request_code_if_email_known(con, email)
    content = f"""
<p class="subtitle">If that email is registered, a code was just sent.</p>
{_code_form(email)}
"""
    return page(content, title="Login")


@router.post(
    "/login/verify",
    status_code=200,
    description="Verify a login code and start a session",
)
def login_verify(con: DBDep, email: str = Form(...), code: str = Form(...)):
    if not service.verify_code(email, code):
        content = f"""
<p class="subtitle">Invalid or expired code.</p>
{_code_form(email)}
"""
        return page(content, title="Login")

    user = users_service.get_by_email(con, email)
    if user is None:
        content = f"""
<p class="subtitle">That account no longer exists.</p>
{_code_form(email)}
"""
        return page(content, title="Login")

    token = service.create_session(con, user["id"])
    response = RedirectResponse(url=f"/{user['username']}/account", status_code=302)
    response.set_cookie(
        service.SESSION_COOKIE_NAME,
        token,
        max_age=int(service.SESSION_TTL.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=True,
    )
    return response


@router.post("/logout", status_code=200, description="End the current session")
def logout(request: Request, con: DBDep):
    token = request.cookies.get(service.SESSION_COOKIE_NAME)
    if token:
        service.delete_session(con, token)
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(service.SESSION_COOKIE_NAME)
    return response
