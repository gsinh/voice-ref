"""Shared infrastructure helpers for voice-ref services.

Deliberately tiny (ADR-0002): settings, logging, health and app bootstrap only.
Domain code never goes here.
"""

from voiceref_common.app import create_app, run
from voiceref_common.health import ReadinessCheck, postgres_check
from voiceref_common.settings import ServiceSettings

__all__ = ["ReadinessCheck", "ServiceSettings", "create_app", "postgres_check", "run"]
