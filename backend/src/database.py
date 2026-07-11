import sqlite3
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends

from src.config import settings


def get_connection() -> sqlite3.Connection:
    con = sqlite3.connect(settings.db_path)
    con.row_factory = sqlite3.Row
    return con


def get_db() -> Generator[sqlite3.Connection, None, None]:
    con = get_connection()
    try:
        yield con
    finally:
        con.close()


DBDep = Annotated[sqlite3.Connection, Depends(get_db)]
