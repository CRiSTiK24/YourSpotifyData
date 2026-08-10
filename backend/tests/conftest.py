import os
import sqlite3

import pytest

_SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "spotifyProcessed",
    "schema.sql",
)


@pytest.fixture
def db():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    with open(_SCHEMA_PATH) as f:
        con.executescript(f.read())
    yield con
    con.close()
