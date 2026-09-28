from pathlib import Path

import pytest
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings

from config_kit import settings_config


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("BANK_DATABASE_URL", "TOKEN_SIGNING_KEY"):
        monkeypatch.delenv(name, raising=False)


def _settings_class() -> type[BaseSettings]:
    class S(BaseSettings):
        model_config = settings_config(env_prefix="BANK_")
        database_url: str = "default"
        key: SecretStr = Field(SecretStr(""), validation_alias="TOKEN_SIGNING_KEY")

    return S


def test_reads_secret_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "BANK_DATABASE_URL").write_text("postgresql://from-file")
    (tmp_path / "TOKEN_SIGNING_KEY").write_text("k" * 40)
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path))
    s = _settings_class()()
    assert s.database_url == "postgresql://from-file"  # type: ignore[attr-defined]
    assert s.key.get_secret_value() == "k" * 40  # type: ignore[attr-defined]


def test_environment_wins_but_empty_values_do_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "BANK_DATABASE_URL").write_text("postgresql://from-file")
    (tmp_path / "TOKEN_SIGNING_KEY").write_text("from-file")
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path))
    monkeypatch.setenv("BANK_DATABASE_URL", "postgresql://from-env")
    monkeypatch.setenv("TOKEN_SIGNING_KEY", "")
    s = _settings_class()()
    assert s.database_url == "postgresql://from-env"  # type: ignore[attr-defined]
    assert s.key.get_secret_value() == "from-file"  # type: ignore[attr-defined]


def test_missing_secrets_dir_is_fine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRETS_DIR", "/nonexistent")
    assert _settings_class()().database_url == "default"  # type: ignore[attr-defined]
