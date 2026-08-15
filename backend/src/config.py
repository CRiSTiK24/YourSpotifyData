import os

from pydantic import model_validator
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
    owner_username: str = ""

    spotify_redirect_uri: str = ""

    scrobbler_poll_seconds: int = 900
    library_sync_poll_seconds: int = 21600

    model_config = {
        "env_file": (
            os.path.join(_BACKEND_DIR, "config.env"),
            os.path.join(_BACKEND_DIR, ".env"),
        )
    }

    @model_validator(mode="after")
    def _default_owner_username(self) -> "Settings":
        if not self.owner_username and self.allowed_email:
            self.owner_username = self.allowed_email.split("@", 1)[0]
        return self


settings = Settings()
