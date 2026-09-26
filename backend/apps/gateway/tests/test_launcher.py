import asyncio
import os
import signal
import sys
import time

import pytest

from gateway.launcher import Process, run, sidecars


def _py(name: str, code: str) -> Process:
    return Process(name, [sys.executable, "-c", code], {})


async def test_one_process_dying_stops_the_rest_with_its_code() -> None:
    started = time.monotonic()
    code = await run(
        [_py("long", "import time; time.sleep(60)"), _py("dies", "raise SystemExit(3)")]
    )
    assert code == 3
    assert time.monotonic() - started < 20  # the long-running one was stopped, not awaited


async def test_a_clean_exit_still_counts_as_failure() -> None:
    # A sidecar that simply exits has stopped doing its job: restart the container.
    assert await run([_py("long", "import time; time.sleep(60)"), _py("quits", "pass")]) == 1


async def test_sigterm_stops_everything_gracefully() -> None:
    loop = asyncio.get_running_loop()
    loop.call_later(0.5, os.kill, os.getpid(), signal.SIGTERM)
    code = await run(
        [_py("a", "import time; time.sleep(60)"), _py("b", "import time; time.sleep(60)")]
    )
    assert code == 0


def test_missing_sidecar_binary_fails_fast_with_a_clear_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LAYA_BIN", "/nonexistent/laya-serve")
    with pytest.raises(SystemExit, match="SIDECARS"):
        sidecars(["laya"])
