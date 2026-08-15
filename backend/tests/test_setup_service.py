from src import setup
from src.setup.service import consume_setup_token, get_or_create_setup_token


def test_get_or_create_setup_token_returns_the_same_value_across_calls(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.service, "SETUP_TOKEN_PATH", str(tmp_path / ".setup_token"))
    first = get_or_create_setup_token()
    second = get_or_create_setup_token()
    assert first == second


def test_consume_setup_token_makes_the_next_call_generate_a_new_one(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.service, "SETUP_TOKEN_PATH", str(tmp_path / ".setup_token"))
    first = get_or_create_setup_token()
    consume_setup_token()
    second = get_or_create_setup_token()
    assert first != second
