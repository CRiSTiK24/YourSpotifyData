import os
import secrets

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
SETUP_TOKEN_PATH = os.path.join(_BACKEND_DIR, ".setup_token")


def get_or_create_setup_token() -> str:
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
