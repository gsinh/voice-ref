"""One settings convention for every component (ADR-0019).

Each setting can come from, in order of precedence:
1. an environment variable (12-factor; how Hugging Face Space and Workers secrets arrive),
2. a *secret file* named after the variable, in SECRETS_DIR (default /run/secrets, where
   Docker mounts compose secrets). Files keep secrets out of `docker inspect`, process
   environments and shell history.

Empty environment variables are ignored, so an unset `FOO=` in compose never hides the
secret file `FOO`.
"""

import os
from typing import Any, cast

from pydantic_settings import SettingsConfigDict

DEFAULT_SECRETS_DIR = "/run/secrets"


def secrets_dir() -> str | None:
    path = os.environ.get("SECRETS_DIR", DEFAULT_SECRETS_DIR)
    return path if os.path.isdir(path) else None


def settings_config(**overrides: Any) -> SettingsConfigDict:
    config: dict[str, Any] = {
        "extra": "ignore",
        "frozen": True,
        "env_ignore_empty": True,
        "secrets_dir": secrets_dir(),
        **overrides,
    }
    return cast(SettingsConfigDict, config)
