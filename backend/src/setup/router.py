import secrets
from html import escape

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from src import app_settings
from src.auth import service as auth_service
from src.database import DBDep
from src.html import page, page_header, widget
from src.users import service as users_service
from src.users.exceptions import UserValidationError

from .service import consume_setup_token, get_or_create_setup_token

router = APIRouter(tags=["setup"])


def _account_field(label: str, name: str, *, type: str = "text", value: str = "", **attrs) -> str:
    attr_str = " ".join(f'{k.replace("_", "-")}="{escape(str(v))}"' for k, v in attrs.items())
    return f"""
<label class="form-field"><span class="subtitle">{escape(label)}</span>
  <input name="{name}" type="{type}" value="{escape(value)}" {attr_str}></label>"""


def _integrations_html(
    *,
    resend_api_key: str = "",
    spotify_client_id: str = "",
    spotify_client_secret: str = "",
    spotify_redirect_uri: str = "",
) -> str:
    resend_section = widget(
        "Email login",
        f"""
<p class="subtitle">Login codes are sent by email via <a href="https://resend.com"
target="_blank" rel="noopener noreferrer">Resend</a>. Leave blank to skip for now -
you won't be able to log in until this is set.</p>
{_account_field("Resend API key", "resend_api_key", value=resend_api_key, placeholder="re_xxxxxxxx")}
""",
    )
    spotify_section = widget(
        "Spotify integration",
        f"""
<p class="subtitle">Register an app in the <a href="https://developer.spotify.com/dashboard"
target="_blank" rel="noopener noreferrer">Spotify Developer Dashboard</a> to enable cover art
and the live scrobbler. Leave blank to skip - both stay unused until this is filled in.</p>
{_account_field("Client ID", "spotify_client_id", value=spotify_client_id)}
{_account_field("Client secret", "spotify_client_secret", value=spotify_client_secret)}
{_account_field("Redirect URI", "spotify_redirect_uri", value=spotify_redirect_uri, placeholder="https://your-domain/<username>/scrobbler/callback")}
<p class="subtitle">Must exactly match what you register in the Spotify dashboard for
your own domain - this can't be guessed for you (a reverse proxy or custom domain
means the app can't reliably tell what the public URL actually is).</p>
""",
    )
    return resend_section + spotify_section


def _create_form_html(error: str | None = None, *, email: str = "", username: str = "") -> str:
    error_html = f"<p class='subtitle'>{escape(error)}</p>" if error else ""
    account_section = widget(
        "Your account",
        f"""
<p class="subtitle">This becomes the owner account - the one with admin access,
able to add up to 4 more accounts later from the Account page.</p>
{error_html}
{_account_field("Email", "email", type="email", value=email, placeholder="you@example.com", required=True)}
{_account_field("Username", "username", value=username, maxlength=64, placeholder="e.g. your first name", required=True)}
{_account_field("Setup token", "setup_token", placeholder="printed in the server logs on startup", required=True)}
<p class="subtitle">Proves you have shell/log access to this server, not just a browser -
check the startup logs (or backend/.setup_token) for a line like "visit /setup and enter
this token...".</p>
""",
    )
    return f"""
{page_header("Set up your instance")}
<form method="post">
<div class="account-sections">
{account_section}
{_integrations_html()}
</div>
<button type="submit" class="btn" style="margin-top:16px">Create owner account</button>
</form>
"""


def _revisit_form_html(con, owner, error: str | None = None, success: str | None = None) -> str:
    message_html = ""
    if error:
        message_html = f"<p class='subtitle'>{escape(error)}</p>"
    elif success:
        message_html = f"<p class='subtitle'>{escape(success)}</p>"
    account_section = widget(
        "Your account",
        f"""
<p class="subtitle">Owner: {escape(owner["username"])} ({escape(owner["email"])}).
Change the username from the Account page instead.</p>
{message_html}
""",
    )
    eff = app_settings.get(con)
    return f"""
{page_header("Instance settings")}
<form method="post">
<div class="account-sections">
{account_section}
{
        _integrations_html(
            resend_api_key=eff.resend_api_key,
            spotify_client_id=eff.spotify_client_id,
            spotify_client_secret=eff.spotify_client_secret,
            spotify_redirect_uri=eff.spotify_redirect_uri,
        )
    }
</div>
<button type="submit" class="btn" style="margin-top:16px">Save</button>
</form>
"""


@router.get("/setup", response_class=HTMLResponse, status_code=200, description="Instance setup")
def setup_form(con: DBDep, request: Request):
    owner = users_service.get_owner(con)
    if owner is None:
        return page(_create_form_html(), title="Setup")
    current = auth_service.get_current_user(request, con)
    if current["role"] != "owner":
        raise HTTPException(status_code=403, detail="Not allowed")
    return page(_revisit_form_html(con, current), title="Setup")


@router.post(
    "/setup",
    response_class=HTMLResponse,
    status_code=200,
    description="Create or update instance setup",
)
def setup_submit(
    con: DBDep,
    request: Request,
    email: str = Form(""),
    username: str = Form(""),
    setup_token: str = Form(""),
    resend_api_key: str = Form(""),
    spotify_client_id: str = Form(""),
    spotify_client_secret: str = Form(""),
    spotify_redirect_uri: str = Form(""),
):
    owner = users_service.get_owner(con)
    if owner is None:
        try:
            if not email.strip() or not username.strip():
                raise UserValidationError("Email and username are both required.")
            if not secrets.compare_digest(setup_token.strip(), get_or_create_setup_token()):
                raise UserValidationError(
                    "Invalid setup token - check the server's startup logs or backend/.setup_token."
                )
            owner = users_service.create_owner(con, username, email)
        except UserValidationError as e:
            return page(_create_form_html(str(e), email=email, username=username), title="Setup")
        users_service.ensure_schema(con)
        consume_setup_token()
        app_settings.update(
            con,
            resend_api_key=resend_api_key,
            spotify_client_id=spotify_client_id,
            spotify_client_secret=spotify_client_secret,
            spotify_redirect_uri=spotify_redirect_uri,
        )
        heading = "Account created"
        body = f"'{escape(owner['username'])}' is now the owner account."
        next_step = f'<a href="/login">Log in</a> with {escape(owner["email"])}.'
    else:
        current = auth_service.get_current_user(request, con)
        if current["role"] != "owner":
            raise HTTPException(status_code=403, detail="Not allowed")
        app_settings.update(
            con,
            resend_api_key=resend_api_key,
            spotify_client_id=spotify_client_id,
            spotify_client_secret=spotify_client_secret,
            spotify_redirect_uri=spotify_redirect_uri,
        )
        heading = "Settings saved"
        body = "Instance settings updated."
        next_step = ""

    next_step_html = f"<p class='subtitle'>{next_step}</p>" if next_step else ""
    return page(
        f"""
{page_header(heading)}
<p class="subtitle">{body}</p>
{next_step_html}
""",
        title=heading,
    )
