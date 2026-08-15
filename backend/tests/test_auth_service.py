from datetime import UTC, datetime, timedelta

import pytest

from src.auth import service as auth_service


@pytest.fixture(autouse=True)
def reset_pending_codes():
    auth_service._pending_codes.clear()
    yield
    auth_service._pending_codes.clear()


def _set_pending_code(
    email="owner@example.com", code="123456", attempts=0, expires_in=timedelta(minutes=5)
):
    auth_service._pending_codes[email] = {
        "code": code,
        "expires_at": datetime.now(UTC) + expires_in,
        "attempts": attempts,
    }


def test_verify_code_rejects_when_no_code_was_ever_requested():
    assert auth_service.verify_code("owner@example.com", "123456") is False


def test_verify_code_accepts_the_correct_code_and_then_clears_it():
    _set_pending_code(code="123456")
    assert auth_service.verify_code("owner@example.com", "123456") is True
    assert auth_service.verify_code("owner@example.com", "123456") is False


def test_verify_code_rejects_an_incorrect_code_and_counts_it_as_an_attempt():
    _set_pending_code(code="123456", attempts=0)
    assert auth_service.verify_code("owner@example.com", "000000") is False
    assert auth_service._pending_codes["owner@example.com"]["attempts"] == 1


def test_verify_code_rejects_an_expired_code_even_if_correct():
    _set_pending_code(code="123456", expires_in=timedelta(minutes=-1))
    assert auth_service.verify_code("owner@example.com", "123456") is False


def test_verify_code_locks_out_after_five_failed_attempts_even_with_the_right_code():
    _set_pending_code(code="123456", attempts=auth_service.MAX_ATTEMPTS)
    assert auth_service.verify_code("owner@example.com", "123456") is False


def test_verify_code_strips_surrounding_whitespace_before_comparing():
    _set_pending_code(code="123456")
    assert auth_service.verify_code("owner@example.com", "  123456  ") is True


def test_verify_code_is_scoped_per_email():
    _set_pending_code(email="owner@example.com", code="111111")
    _set_pending_code(email="member@example.com", code="222222")
    assert auth_service.verify_code("owner@example.com", "222222") is False
    assert auth_service.verify_code("member@example.com", "222222") is True
