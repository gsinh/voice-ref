import pytest


@pytest.fixture(autouse=True)
def _required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings that have no default (fail-fast secrets) get test values."""
    monkeypatch.setenv("TOKEN_SIGNING_KEY", "test-signing-key-" + "x" * 32)
