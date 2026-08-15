from datetime import UTC, datetime, timedelta

import pytest

from src.scrobbler import service as scrobbler_service
from src.scrobbler.exceptions import NotConnected


def _insert_token(db, user_id, expires_at, access_token="old-token", refresh_token="refresh-tok"):
    db.execute(
        "INSERT INTO scrobbler_tokens (user_id, access_token, refresh_token, expires_at, connected_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            user_id,
            access_token,
            refresh_token,
            expires_at.isoformat(),
            datetime.now(UTC).isoformat(),
        ),
    )
    db.commit()


def test_ensure_access_token_raises_not_connected_when_no_account_is_linked(db, user_id):
    with pytest.raises(NotConnected):
        scrobbler_service.ensure_access_token(db, user_id)


def test_ensure_access_token_returns_the_stored_token_when_not_yet_expired(db, user_id):
    _insert_token(
        db, user_id, expires_at=datetime.now(UTC) + timedelta(minutes=30), access_token="valid"
    )
    assert scrobbler_service.ensure_access_token(db, user_id) == "valid"


def test_ensure_access_token_refreshes_and_persists_a_new_token_once_expired(
    db, user_id, monkeypatch
):
    _insert_token(
        db,
        user_id,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
        access_token="stale",
        refresh_token="my-refresh-token",
    )
    monkeypatch.setattr(
        scrobbler_service,
        "_post_token_request",
        lambda con, data: {"access_token": "fresh-token", "expires_in": 3600},
    )

    result = scrobbler_service.ensure_access_token(db, user_id)

    assert result == "fresh-token"
    stored = db.execute(
        "SELECT access_token FROM scrobbler_tokens WHERE user_id = ?", (user_id,)
    ).fetchone()
    assert stored["access_token"] == "fresh-token"


def test_ensure_access_token_does_not_use_another_users_token(db, user_id, other_user_id):
    _insert_token(
        db,
        other_user_id,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        access_token="theirs",
    )
    with pytest.raises(NotConnected):
        scrobbler_service.ensure_access_token(db, user_id)
