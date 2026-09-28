import subprocess
import sys


def test_agent_module_is_not_imported_before_the_agent_name_is_set() -> None:
    """Regression: importing the agent registers the entrypoint, which reads
    LIVEKIT_AGENT_NAME at that moment. __main__ must set it before importing."""
    probe = "import sys, voice_worker.__main__; print('voice_worker.agent' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


def test_agent_registers_under_the_configured_name() -> None:
    probe = (
        "import os; os.environ['LIVEKIT_AGENT_NAME'] = 'bank-agent'; "
        "from voice_worker import agent; print(agent.server._agent_name)"
    )
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert out.stdout.strip().splitlines()[-1] == "bank-agent"
