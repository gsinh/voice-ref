"""Conversation orchestrator: LangGraph graph exposed over HTTP for text and voice.

Phase 0: health endpoints only. Phase 1 adds the LangGraph graph and /chat.
"""

from orchestrator.settings import get_settings
from voiceref_common import create_app, postgres_check

settings = get_settings()
app = create_app(settings, {"postgres": postgres_check(settings.database_url)})
