import os

from pydantic_settings import BaseSettings

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))


class Settings(BaseSettings):
    # Non-secret settings — safe to look at, just environment-specific.
    db_path: str = os.path.join(_BASE_DIR, "data", "spotifyProcessed", "SpotifyData.db")
    resend_from: str = "onboarding@resend.dev"

    # Secrets/access-control — never committed. Used by
    # processors/SpotifyImageFetcher.py (Client Credentials flow) and by the
    # scrobbler's OAuth Authorization Code flow. Optional so the app still
    # starts without them (whichever feature needs them just stays unusable).
    spotify_client_id: str = ""
    spotify_client_secret: str = ""

    # Email-code login gating the /upload and /scrobbler flows. Optional so
    # the app still starts without them (those routes just stay unusable).
    allowed_email: str = ""
    resend_api_key: str = ""

    # OAuth callback URL registered in the Spotify Developer Dashboard, e.g.
    # https://cristik.duckdns.org/scrobbler/callback
    spotify_redirect_uri: str = ""

    # How often the background scrobbler poller checks recently-played.
    scrobbler_poll_seconds: int = 900

    model_config = {
        "env_file": (
            os.path.join(_BACKEND_DIR, "config.env"),
            os.path.join(_BACKEND_DIR, ".env"),
        )
    }


settings = Settings()
