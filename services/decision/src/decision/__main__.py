from decision.settings import get_settings
from voiceref_common import run

run("decision.main:app", get_settings())
