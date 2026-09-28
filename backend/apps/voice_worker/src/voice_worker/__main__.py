"""Run the voice worker: `python -m voice_worker` (started as a sidecar by the launcher).

It registers with LiveKit (Cloud or self-hosted) and waits for calls dispatched to
LIVEKIT_AGENT_NAME. Fails fast when LiveKit isn't configured.
"""

import os
import sys

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
    # LiveKit reads the agent name when the entrypoint is registered, i.e. when the agent
    # module is imported. Set it first, import after: otherwise the worker registers with
    # no name and explicit dispatch to "bank-agent" never reaches it.
    os.environ.setdefault("LIVEKIT_AGENT_NAME", settings.agent_name)
    from livekit.agents.__main__ import main as livekit_main

    from voice_worker import agent

    agent.check_stt_model(settings)
    if settings.tts_provider == "kokoro":
        # Download once, here, before worker processes start: a process must initialise
        # within seconds, far less than a first-time model download takes.
        from voice_worker.kokoro_tts import ensure_model_files

        ensure_model_files(settings.kokoro_dir, settings.kokoro_model)
    sys.exit(livekit_main(["start", agent.__file__]))


if __name__ == "__main__":
    main()
