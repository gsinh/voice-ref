from banking_api.settings import get_settings
from voiceref_common import run

run("banking_api.main:app", get_settings())
