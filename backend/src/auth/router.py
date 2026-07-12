from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.database import DBDep
from src.html import page

from . import service

router = APIRouter(tags=["auth"])

_CODE_FORM = """
<h1>Enter your code</h1>
<p class="subtitle">Check your email for a 6-digit code (expires in 5 minutes).</p>
<form class="search-form" action="/login/verify" method="post">
  <input name="code" type="text" inputmode="numeric" maxlength="6" placeholder="123456" autofocus>
  <button type="submit">Verify</button>
</form>
"""


@router.get("/login", response_class=HTMLResponse, status_code=200, description="Login form")
def login_form():
    content = """
<h1>Login</h1>
<form class="search-form" action="/login" method="post">
  <input name="email" type="email" placeholder="you@example.com" autofocus required>
  <button type="submit">Send code</button>
</form>
"""
    return page(content)


@router.post(
    "/login", response_class=HTMLResponse, status_code=200, description="Request a login code"
)
def login_submit(email: str = Form(...)):
    service.request_code(email)
    content = f"""
<p class="subtitle">If that email is registered, a code was just sent.</p>
{_CODE_FORM}
"""
    return page(content)


@router.post(
    "/login/verify",
    status_code=200,
    description="Verify a login code and start a session",
)
def login_verify(con: DBDep, code: str = Form(...)):
    if not service.verify_code(code):
        content = f"""
<p class="subtitle">Invalid or expired code.</p>
{_CODE_FORM}
"""
        return page(content)

    token = service.create_session(con)
    response = RedirectResponse(url="/upload", status_code=302)
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
