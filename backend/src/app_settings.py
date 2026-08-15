import sqlite3
from dataclasses import dataclass

from src.config import settings


@dataclass
class EffectiveSettings:
    resend_api_key: str
    spotify_client_id: str
    spotify_client_secret: str
    spotify_redirect_uri: str


def ensure_schema(con: sqlite3.Connection) -> None:
    con.execute(
        "CREATE TABLE IF NOT EXISTS app_settings ("
        "id INTEGER PRIMARY KEY CHECK (id = 1), "
        "resend_api_key TEXT, "
        "spotify_client_id TEXT, "
        "spotify_client_secret TEXT, "
        "spotify_redirect_uri TEXT)"
    )
    con.commit()


def get(con: sqlite3.Connection) -> EffectiveSettings:
    row = con.execute("SELECT * FROM app_settings WHERE id = 1").fetchone()
    return EffectiveSettings(
        resend_api_key=(row["resend_api_key"] if row else None) or settings.resend_api_key,
        spotify_client_id=(row["spotify_client_id"] if row else None) or settings.spotify_client_id,
        spotify_client_secret=(row["spotify_client_secret"] if row else None)
        or settings.spotify_client_secret,
        spotify_redirect_uri=(row["spotify_redirect_uri"] if row else None)
        or settings.spotify_redirect_uri,
    )


def update(con: sqlite3.Connection, **fields: str) -> None:
    values = {k: v.strip() for k, v in fields.items() if v and v.strip()}
    if not values:
        return
    columns = ", ".join(values)
    placeholders = ", ".join("?" for _ in values)
    update_clause = ", ".join(f"{k} = excluded.{k}" for k in values)
    con.execute(
        f"INSERT INTO app_settings (id, {columns}) VALUES (1, {placeholders}) "
        f"ON CONFLICT(id) DO UPDATE SET {update_clause}",
        list(values.values()),
    )
    con.commit()
