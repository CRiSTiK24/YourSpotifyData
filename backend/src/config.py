import os

from pydantic_settings import BaseSettings

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))


class Settings(BaseSettings):
    db_path: str = os.path.join(_BASE_DIR, "data", "spotifyProcessed", "SpotifyData.db")
    resend_from: str = "onboarding@resend.dev"

    spotify_client_id: str = ""
    spotify_client_secret: str = ""

    allowed_email: str = ""
    resend_api_key: str = ""

    spotify_redirect_uri: str = ""

    scrobbler_poll_seconds: int = 900
    library_sync_poll_seconds: int = 21600

    model_config = {
        "env_file": (
            os.path.join(_BACKEND_DIR, "config.env"),
            os.path.join(_BACKEND_DIR, ".env"),
        )
    }


settings = Settings()
