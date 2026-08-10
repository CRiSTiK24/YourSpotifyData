from datetime import UTC, datetime, timedelta

import pytest

from src.scrobbler import service as scrobbler_service
from src.scrobbler.exceptions import NotConnected


def _insert_token(db, expires_at, access_token="old-token", refresh_token="refresh-tok"):
    db.execute(
        "INSERT INTO scrobbler_tokens (id, access_token, refresh_token, expires_at, connected_at) "
        "VALUES (1, ?, ?, ?, ?)",
        (access_token, refresh_token, expires_at.isoformat(), datetime.now(UTC).isoformat()),
    )
    db.commit()


def test_ensure_access_token_raises_not_connected_when_no_account_is_linked(db):
    with pytest.raises(NotConnected):
        scrobbler_service.ensure_access_token(db)


def test_ensure_access_token_returns_the_stored_token_when_not_yet_expired(db):
    _insert_token(db, expires_at=datetime.now(UTC) + timedelta(minutes=30), access_token="valid")
    assert scrobbler_service.ensure_access_token(db) == "valid"


def test_ensure_access_token_refreshes_and_persists_a_new_token_once_expired(db, monkeypatch):
    _insert_token(
        db,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
        access_token="stale",
        refresh_token="my-refresh-token",
    )
    monkeypatch.setattr(
        scrobbler_service,
        "_post_token_request",
        lambda data: {"access_token": "fresh-token", "expires_in": 3600},
    )

    result = scrobbler_service.ensure_access_token(db)

    assert result == "fresh-token"
    stored = db.execute("SELECT access_token FROM scrobbler_tokens WHERE id = 1").fetchone()
    assert stored["access_token"] == "fresh-token"
