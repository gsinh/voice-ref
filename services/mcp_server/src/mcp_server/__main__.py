from mcp_server.settings import get_settings
from voiceref_common import run

run("mcp_server.main:app", get_settings())
