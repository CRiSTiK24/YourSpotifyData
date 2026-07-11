import sqlite3
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends

from src.config import settings


def get_connection() -> sqlite3.Connection:
    # check_same_thread=False: async routes (e.g. upload) resolve this
    # dependency in a different worker thread than the endpoint body runs
    # in. Each request still gets its own fresh connection, closed at the
    # end of the request, so there's no real concurrent-use risk.
    con = sqlite3.connect(settings.db_path, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def get_db() -> Generator[sqlite3.Connection, None, None]:
    con = get_connection()
    try:
        yield con
    finally:
        con.close()


DBDep = Annotated[sqlite3.Connection, Depends(get_db)]
