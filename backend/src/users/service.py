import re
import sqlite3
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from src.config import settings
from src.database import DBDep

from .exceptions import UserValidationError

MAX_USERS = 5

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{1,64}$")

# top-level path segments already owned by global (non-per-user) routes -
# see main.py's app.include_router calls for auth/covers/previews/static -
# plus "admin", which every user's own /{username}/admin route would shadow
# if someone were allowed to name themselves that.
RESERVED_USERNAMES = {"login", "logout", "static", "cover", "preview", "favicon.ico", "admin"}

# Tables that were single-tenant before multiuser support and need a
# user_id column backfilled to the owner for any pre-existing rows.
_USER_SCOPED_TABLES = (
    "track_history",
    "library_tracks",
    "library_albums",
    "library_artists",
    "playlists",
    "playlist_tracks",
    "import_jobs",
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    return (
        con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
        is not None
    )


def _has_column(con: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row["name"] == column for row in con.execute(f"PRAGMA table_info({table})"))


def ensure_schema(con: sqlite3.Connection) -> None:
    con.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "username TEXT NOT NULL UNIQUE, "
        "email TEXT NOT NULL UNIQUE, "
        "role TEXT NOT NULL CHECK (role IN ('owner','member')), "
        "created_at TEXT NOT NULL)"
    )

    owner = con.execute("SELECT * FROM users WHERE role = 'owner'").fetchone()
    if owner is None:
        legacy_username = None
        if _table_exists(con, "app_profile"):
            row = con.execute("SELECT username FROM app_profile WHERE id = 1").fetchone()
            legacy_username = row["username"] if row else None
        # Only fabricate an owner from env-var settings for an existing
        # install being upgraded (a legacy app_profile row proves one was
        # already running) or one that's fully pre-configured via env vars.
        # A genuinely fresh clone with blank settings is left owner-less on
        # purpose - main.py's auth_state_middleware gates every route to
        # /setup until someone actually creates the owner there, rather
        # than silently running with an owner whose username is "".
        if legacy_username or (settings.owner_username and settings.allowed_email):
            con.execute(
                "INSERT INTO users (username, email, role, created_at) VALUES (?, ?, 'owner', ?)",
                (legacy_username or settings.owner_username, settings.allowed_email, _now_iso()),
            )
            con.commit()
            owner = con.execute("SELECT * FROM users WHERE role = 'owner'").fetchone()

    con.execute("DROP TABLE IF EXISTS app_profile")

    if owner is None:
        con.commit()
        return

    for table in _USER_SCOPED_TABLES:
        if not _has_column(con, table, "user_id"):
            con.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER")
        con.execute(f"UPDATE {table} SET user_id = ? WHERE user_id IS NULL", (owner["id"],))
        con.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_user_id ON {table}(user_id)")

    if not _has_column(con, "sessions", "user_id"):
        con.execute("DROP TABLE IF EXISTS sessions")
        con.execute(
            "CREATE TABLE IF NOT EXISTS sessions ("
            "token TEXT PRIMARY KEY, "
            "user_id INTEGER NOT NULL REFERENCES users(id), "
            "created_at TEXT NOT NULL, "
            "expires_at TEXT NOT NULL)"
        )

    con.commit()

    # Without stats, SQLite's planner has no way to know the new user_id
    # indexes above are far less selective than the existing (name, singer)
    # index on track_history, and picks them instead for queries filtering
    # on both - turning an index lookup into a near-full-table scan per row
    # (measured: ~3s per playlist on 238k rows, vs ~2ms after ANALYZE).
    # Cheap enough (this DB's scale) to just always run after a schema change.
    con.execute("ANALYZE")


def get_by_username(con: sqlite3.Connection, username: str) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def get_by_id(con: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_by_email(con: sqlite3.Connection, email: str) -> sqlite3.Row | None:
    return con.execute(
        "SELECT * FROM users WHERE lower(email) = lower(?)", (email.strip(),)
    ).fetchone()


def get_owner(con: sqlite3.Connection) -> sqlite3.Row:
    return con.execute("SELECT * FROM users WHERE role = 'owner'").fetchone()


def list_users(con: sqlite3.Connection) -> list[sqlite3.Row]:
    return con.execute("SELECT * FROM users ORDER BY role DESC, created_at").fetchall()


def validate_username(
    con: sqlite3.Connection, username: str, *, exclude_user_id: int | None = None
) -> str:
    username = username.strip()
    if not _USERNAME_RE.fullmatch(username):
        raise UserValidationError(
            "Username must be 1-64 characters: letters, numbers, '.', '_' or '-'."
        )
    if username.lower() in RESERVED_USERNAMES:
        raise UserValidationError(f"'{username}' is reserved and can't be used.")
    existing = get_by_username(con, username)
    if existing is not None and existing["id"] != exclude_user_id:
        raise UserValidationError(f"'{username}' is already taken.")
    return username


def set_username(con: sqlite3.Connection, user_id: int, username: str) -> str:
    username = validate_username(con, username, exclude_user_id=user_id)
    con.execute("UPDATE users SET username = ? WHERE id = ?", (username, user_id))
    con.commit()
    return username


def create_owner(con: sqlite3.Connection, username: str, email: str) -> sqlite3.Row:
    if get_owner(con) is not None:
        raise UserValidationError("An owner account already exists.")
    username = validate_username(con, username)
    email = email.strip()
    if "@" not in email:
        raise UserValidationError("Enter a valid email address.")
    if get_by_email(con, email) is not None:
        raise UserValidationError(f"'{email}' is already registered.")
    con.execute(
        "INSERT INTO users (username, email, role, created_at) VALUES (?, ?, 'owner', ?)",
        (username, email, _now_iso()),
    )
    con.commit()
    return get_by_username(con, username)


def add_member(con: sqlite3.Connection, username: str, email: str) -> sqlite3.Row:
    count = con.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    if count >= MAX_USERS:
        raise UserValidationError(f"Already at the {MAX_USERS}-user limit.")
    username = validate_username(con, username)
    email = email.strip()
    if "@" not in email:
        raise UserValidationError("Enter a valid email address.")
    if get_by_email(con, email) is not None:
        raise UserValidationError(f"'{email}' is already registered.")
    con.execute(
        "INSERT INTO users (username, email, role, created_at) VALUES (?, ?, 'member', ?)",
        (username, email, _now_iso()),
    )
    con.commit()
    return get_by_username(con, username)


def remove_member(con: sqlite3.Connection, user_id: int) -> None:
    user = get_by_id(con, user_id)
    if user is None or user["role"] == "owner":
        raise UserValidationError("Can't remove the owner account.")
    con.execute("DELETE FROM users WHERE id = ?", (user_id,))
    con.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    con.execute("DELETE FROM scrobbler_tokens WHERE user_id = ?", (user_id,))
    con.commit()


def resolve_viewed_user(request: Request, con: DBDep) -> sqlite3.Row | None:
    """Returns None when mounted at a root, no-username path (the aggregate,
    all-users views - see main.py's app.include_router calls without a
    "/{username}" prefix), rather than requiring a username segment that
    doesn't exist on those routes."""
    username = request.path_params.get("username")
    if username is None:
        return None
    user = get_by_username(con, username)
    if user is None:
        raise HTTPException(status_code=404, detail="Not found")
    return user


ViewedUserDep = Annotated[sqlite3.Row | None, Depends(resolve_viewed_user)]
