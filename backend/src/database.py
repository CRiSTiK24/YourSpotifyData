import os
import sqlite3
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends

from src.config import settings

_SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "spotifyProcessed",
    "schema.sql",
)


def get_connection() -> sqlite3.Connection:
    con = sqlite3.connect(settings.db_path, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def ensure_base_schema(con: sqlite3.Connection) -> None:
    """Applies schema.sql unconditionally - every statement in it is already
    CREATE TABLE/INDEX/TRIGGER IF NOT EXISTS, so this is a no-op against an
    existing database and the only thing that makes a genuinely fresh clone
    (no SpotifyData.db yet) bootable at all, rather than crashing on the
    first query against a table that was never created."""
    with open(_SCHEMA_PATH) as f:
        con.executescript(f.read())


def get_db() -> Generator[sqlite3.Connection, None, None]:
    con = get_connection()
    try:
        yield con
    finally:
        con.close()


DBDep = Annotated[sqlite3.Connection, Depends(get_db)]
