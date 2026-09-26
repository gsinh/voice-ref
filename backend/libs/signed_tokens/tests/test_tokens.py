import time

import jwt
import pytest

from signed_tokens import (
    TokenError,
    issue_confirmation,
    issue_session,
    verify_confirmation,
    verify_session,
)

KEY = "k" * 32
OTHER_KEY = "o" * 32


def test_session_round_trip() -> None:
    assert verify_session(KEY, issue_session(KEY, "CUST-1")).customer_id == "CUST-1"


def test_session_rejects_wrong_key_and_expiry() -> None:
    with pytest.raises(TokenError):
        verify_session(OTHER_KEY, issue_session(KEY, "CUST-1"))
    with pytest.raises(TokenError):
        verify_session(KEY, issue_session(KEY, "CUST-1", ttl_s=-1))


def test_tokens_are_not_interchangeable() -> None:
    confirmation = issue_confirmation(KEY, "CUST-1", "block_card", "CARD-1")
    with pytest.raises(TokenError):
        verify_session(KEY, confirmation)
    with pytest.raises(TokenError):
        verify_confirmation(
            KEY, issue_session(KEY, "CUST-1"), customer_id="CUST-1", action="x", target="y"
        )


def test_confirmation_is_bound_to_customer_action_and_target() -> None:
    token = issue_confirmation(KEY, "CUST-1", "block_card", "CARD-1")
    ok = verify_confirmation(KEY, token, customer_id="CUST-1", action="block_card", target="CARD-1")
    assert ok.token_id
    for wrong in (
        {"customer_id": "CUST-2", "action": "block_card", "target": "CARD-1"},
        {"customer_id": "CUST-1", "action": "close_account", "target": "CARD-1"},
        {"customer_id": "CUST-1", "action": "block_card", "target": "CARD-2"},
    ):
        with pytest.raises(TokenError):
            verify_confirmation(KEY, token, **wrong)


def test_each_confirmation_has_a_unique_id() -> None:
    a = issue_confirmation(KEY, "C", "block_card", "T")
    b = issue_confirmation(KEY, "C", "block_card", "T")
    ids = {
        verify_confirmation(KEY, t, customer_id="C", action="block_card", target="T").token_id
        for t in (a, b)
    }
    assert len(ids) == 2


def test_rejects_unsigned_token() -> None:
    claims = {"sub": "CUST-1", "exp": int(time.time()) + 60}
    forged = jwt.encode(claims, key=None, algorithm="none")  # type: ignore[arg-type]
    with pytest.raises(TokenError):
        verify_session(KEY, forged)


def test_short_keys_are_refused() -> None:
    with pytest.raises(ValueError):
        issue_session("short", "CUST-1")
