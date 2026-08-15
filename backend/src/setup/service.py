import os
import secrets

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
SETUP_TOKEN_PATH = os.path.join(_BACKEND_DIR, ".setup_token")


def get_or_create_setup_token() -> str:
    """A random token required to complete first-run setup, so claiming the
    owner account needs filesystem/log access to this server, not just being
    the first person to reach the site over HTTP. Persisted to disk rather
    than regenerated per process so it survives a restart before setup is
    completed."""
    if os.path.exists(SETUP_TOKEN_PATH):
        with open(SETUP_TOKEN_PATH) as f:
            token = f.read().strip()
        if token:
            return token
    token = secrets.token_urlsafe(24)
    with open(SETUP_TOKEN_PATH, "w") as f:
        f.write(token)
    return token


def consume_setup_token() -> None:
    if os.path.exists(SETUP_TOKEN_PATH):
        os.remove(SETUP_TOKEN_PATH)
