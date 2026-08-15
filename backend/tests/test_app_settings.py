from src import app_settings


def test_get_falls_back_to_env_settings_when_db_row_is_empty(db, monkeypatch):
    app_settings.ensure_schema(db)
    monkeypatch.setattr(app_settings.settings, "resend_api_key", "env-resend-key")
    monkeypatch.setattr(app_settings.settings, "spotify_client_id", "env-client-id")

    eff = app_settings.get(db)

    assert eff.resend_api_key == "env-resend-key"
    assert eff.spotify_client_id == "env-client-id"


def test_update_then_get_returns_the_db_value_over_the_env_fallback(db, monkeypatch):
    app_settings.ensure_schema(db)
    monkeypatch.setattr(app_settings.settings, "resend_api_key", "env-resend-key")

    app_settings.update(db, resend_api_key="db-resend-key")

    assert app_settings.get(db).resend_api_key == "db-resend-key"


def test_update_skips_blank_values_so_an_empty_field_keeps_the_saved_one(db):
    app_settings.ensure_schema(db)
    app_settings.update(db, resend_api_key="keep-me")

    app_settings.update(db, resend_api_key="   ", spotify_client_id="")

    assert app_settings.get(db).resend_api_key == "keep-me"


def test_update_only_touches_the_fields_it_was_given(db):
    app_settings.ensure_schema(db)
    app_settings.update(db, resend_api_key="resend-value")

    app_settings.update(db, spotify_client_id="client-value")

    eff = app_settings.get(db)
    assert eff.resend_api_key == "resend-value"
    assert eff.spotify_client_id == "client-value"
