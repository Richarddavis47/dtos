"""Explicit canonical price semantics for historical source controls."""
import json
from src.core.historical_intelligence import GlobalMarketCheckpoint
from src.core.valuation.config import NORMALIZATION_VERSION
from src.core.valuation.consensus import MARKET_SELECTION_VERSION
from src.core.valuation.observation_identity import OBSERVATION_IDENTITY_VERSION


def canonical_quote(player, value=500, **overrides):
    formats = json.dumps([{'provider': 'DynastyProcess', 'format': 'dynasty_2qb',
                          'details': None, 'source_scale': '0-10000',
                          'normalization': NORMALIZATION_VERSION}], sort_keys=True, separators=(',', ':'))
    fields = dict(asset_id=player, normalized_value=value, provider='DynastyProcess',
                  occurred_at='2025-09-30T12:00:00Z', confidence=90,
                  classification='event_relevant', reason_codes=('trade',),
                  source_reference='supported-source-generation', market_context_id='historical-market',
                  normalization_version=NORMALIZATION_VERSION, value_concept='canonical_market',
                  comparison_identity=('external_market_normalized_index', '0-1000', formats,
                      MARKET_SELECTION_VERSION + ':' + OBSERVATION_IDENTITY_VERSION, 'DynastyProcess'))
    fields.update(overrides)
    return GlobalMarketCheckpoint.create(**fields)
