import os

from pydantic_settings import BaseSettings

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


class Settings(BaseSettings):
    db_path: str = os.path.join(_BASE_DIR, "data", "spotifyProcessed", "SpotifyData.db")

    model_config = {"env_file": os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")}


settings = Settings()
