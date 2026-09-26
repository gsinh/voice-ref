"""System-1 decisions with the Laya model (ADR-0005).

Phase 1 loads Laya (ONNX) and adds /decide.
"""

from decision.router import create_router
from decision.settings import Settings

__all__ = ["Settings", "create_router"]
