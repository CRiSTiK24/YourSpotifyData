from src.users import service as users_service


def test_ensure_schema_leaves_no_owner_when_settings_are_blank(db, monkeypatch):
    monkeypatch.setattr(users_service.settings, "owner_username", "")
    monkeypatch.setattr(users_service.settings, "allowed_email", "")

    users_service.ensure_schema(db)

    assert users_service.get_owner(db) is None


def test_ensure_schema_still_auto_creates_owner_when_both_settings_are_set(db, monkeypatch):
    monkeypatch.setattr(users_service.settings, "owner_username", "alice")
    monkeypatch.setattr(users_service.settings, "allowed_email", "alice@example.com")

    users_service.ensure_schema(db)

    owner = users_service.get_owner(db)
    assert owner is not None
    assert owner["username"] == "alice"
    assert owner["email"] == "alice@example.com"


def test_ensure_schema_migrates_user_scoped_tables_once_an_owner_exists(db, monkeypatch):
    monkeypatch.setattr(users_service.settings, "owner_username", "alice")
    monkeypatch.setattr(users_service.settings, "allowed_email", "alice@example.com")

    users_service.ensure_schema(db)

    owner_id = users_service.get_owner(db)["id"]
    row = db.execute("PRAGMA table_info(track_history)").fetchall()
    assert any(col["name"] == "user_id" for col in row)
    db.execute(
        "INSERT INTO track_history (user_id, name, singer, time) VALUES (?, 'Song', 'Artist', ?)",
        (owner_id, "2024-01-01T00:00:00"),
    )
