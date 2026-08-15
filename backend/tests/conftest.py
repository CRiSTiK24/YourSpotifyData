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


@pytest.fixture
def user_id(db):
    cur = db.execute(
        "INSERT INTO users (username, email, role, created_at) "
        "VALUES ('owner', 'owner@example.com', 'owner', '2024-01-01T00:00:00Z')"
    )
    db.commit()
    return cur.lastrowid


@pytest.fixture
def other_user_id(db):
    cur = db.execute(
        "INSERT INTO users (username, email, role, created_at) "
        "VALUES ('member', 'member@example.com', 'member', '2024-01-01T00:00:00Z')"
    )
    db.commit()
    return cur.lastrowid
