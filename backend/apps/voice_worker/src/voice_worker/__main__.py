"""Run the voice worker: `python -m voice_worker` (started as a sidecar by the launcher).

It registers with LiveKit (Cloud or self-hosted) and waits for calls dispatched to
LIVEKIT_AGENT_NAME. Fails fast when LiveKit isn't configured.
"""

import os
import sys

from livekit.agents.__main__ import main as livekit_main

from voice_worker import agent
from voice_worker.settings import get_settings


def main() -> None:
    settings = get_settings()
    missing = [
        name
        for name, value in (
            ("LIVEKIT_URL", settings.livekit_url),
            ("LIVEKIT_API_KEY", settings.livekit_api_key.get_secret_value()),
            ("LIVEKIT_API_SECRET", settings.livekit_api_secret.get_secret_value()),
        )
        if not value
    ]
    if missing:
        raise SystemExit(
            f"voice worker needs {', '.join(missing)}; set them or drop 'voice' from SIDECARS"
        )
    os.environ.setdefault("LIVEKIT_AGENT_NAME", settings.agent_name)
    agent.check_stt_model(settings)
    sys.exit(livekit_main(["start", agent.__file__]))


if __name__ == "__main__":
    main()
