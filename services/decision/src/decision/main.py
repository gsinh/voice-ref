"""System-1 decision service wrapping the Laya model (ADR-0005).

Phase 0: health endpoints only. Phase 1 loads Laya (ONNX) and adds /decide.
"""

from decision.settings import get_settings
from voiceref_common import create_app

app = create_app(get_settings())
