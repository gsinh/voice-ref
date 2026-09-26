"""Process launcher for the backend container (ADR-0017).

The container runs the gateway plus sidecars (Laya now; agentgateway and the voice worker
later). The rule is *shared fate*: if any process exits, stop the rest and exit with its
code, so the platform (Docker, Hugging Face) restarts the whole container cleanly
instead of leaving it half-alive. SIGTERM/SIGINT are forwarded so every process gets a
graceful shutdown.
"""

import asyncio
import logging
import os
import shutil
import signal
import sys
from dataclasses import dataclass

log = logging.getLogger(__name__)

STOP_TIMEOUT_S = 15


@dataclass(frozen=True)
class Process:
    name: str
    argv: list[str]
    env: dict[str, str]


def sidecars(names: list[str]) -> list[Process]:
    """Sidecars enabled by the SIDECARS env var (comma-separated)."""
    known = {
        # Laya's own HTTP server, installed in its own virtualenv (/opt/laya) so PyTorch
        # never enters the app's dependency tree. Localhost only.
        "laya": Process(
            "laya",
            [os.environ.get("LAYA_BIN", "/opt/laya/bin/laya-serve")],
            {
                "LAYA_HOST": "127.0.0.1",
                "LAYA_PORT": os.environ.get("LAYA_PORT", "8100"),
                "LAYA_DEVICE": os.environ.get("LAYA_DEVICE", "cpu"),
                "LAYA_PRELOAD": "1",
                "LAYA_MODELS": os.environ.get("LAYA_MODELS", "english,multilingual"),
                "LAYA_THREADS": os.environ.get("LAYA_THREADS", "2"),
            },
        ),
        # The LiveKit voice worker: connects out to LiveKit and sends each caller turn to
        # this container's /api/chat. Same interpreter and virtualenv as the gateway.
        "voice": Process("voice", [sys.executable, "-m", "voice_worker"], {}),
    }
    unknown = [n for n in names if n not in known]
    if unknown:
        raise SystemExit(f"unknown sidecar(s) {unknown}; known: {sorted(known)}")
    chosen = [known[n] for n in names]
    for p in chosen:
        if not shutil.which(p.argv[0]):
            raise SystemExit(
                f"sidecar {p.name!r} is enabled but {p.argv[0]} is missing "
                f"(image built without it?). Set SIDECARS to exclude it."
            )
    return chosen


async def run(processes: list[Process]) -> int:
    children: dict[str, asyncio.subprocess.Process] = {}
    for p in processes:
        children[p.name] = await asyncio.create_subprocess_exec(
            *p.argv, env={**os.environ, **p.env}
        )
        log.info("process started", extra={"child": p.name, "pid": children[p.name].pid})

    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stopping.set)

    waits = {asyncio.create_task(c.wait()): name for name, c in children.items()}
    stop_task = asyncio.create_task(stopping.wait())
    done, _ = await asyncio.wait([*waits, stop_task], return_when=asyncio.FIRST_COMPLETED)

    exit_code = 0
    for task in done:
        if task in waits:
            exit_code = task.result() or 1  # a sidecar exiting at all is a failure
            log.error("process exited", extra={"child": waits[task], "code": task.result()})

    for name, child in children.items():
        if child.returncode is None:
            child.send_signal(signal.SIGTERM)
            log.info("stopping process", extra={"child": name})
    try:
        await asyncio.wait_for(
            asyncio.gather(*(c.wait() for c in children.values())), STOP_TIMEOUT_S
        )
    except TimeoutError:
        for child in children.values():
            if child.returncode is None:
                child.kill()
    # 0 after a requested stop; otherwise the code of the process that died first.
    return exit_code


def main() -> None:
    names = [n.strip() for n in os.environ.get("SIDECARS", "").split(",") if n.strip()]
    gateway = Process("gateway", [sys.executable, "-m", "gateway", "serve"], {})
    sys.exit(asyncio.run(run([gateway, *sidecars(names)])))
