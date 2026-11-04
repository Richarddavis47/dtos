"""Canonical GM Behavioral Intelligence boundary."""

from .models import (
    GM_BEHAVIOR_METHOD_VERSION, GM_BEHAVIOR_SCHEMA_VERSION,
    BehavioralDimension, GMBehavioralProfile,
)
from .service import (
    GMBehavioralIntelligenceService, gm_behavioral_intelligence,
    publish_gm_behavioral_intelligence,
)

__all__ = (
    "GM_BEHAVIOR_METHOD_VERSION", "GM_BEHAVIOR_SCHEMA_VERSION",
    "BehavioralDimension", "GMBehavioralProfile",
    "GMBehavioralIntelligenceService", "gm_behavioral_intelligence",
    "publish_gm_behavioral_intelligence",
)
