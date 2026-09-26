from orchestrator.settings import get_settings
from voiceref_common import run

run("orchestrator.main:app", get_settings())
