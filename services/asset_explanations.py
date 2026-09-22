"""Presentation adapters; no provider reads, scoring or historical reconstruction."""
from hashlib import sha256
import json

from src.core.explanations import (
    Availability as A, EvidenceContext, EvidenceItem, EvidenceKind as K,
    Explanation, Statement,
)


def _build(subject, family, league_id, scope, rows, conclusion, *, limits=(), advanced=()):
    # Some accepted reports have no single upstream generation (e.g. source
    # projection plus context). This is explicitly a PRESENTATION fingerprint,
    # not a fabricated source generation, timestamp or freshness observation.
    fingerprint = sha256(json.dumps([scope, rows, conclusion, limits, advanced], sort_keys=True, default=str).encode()).hexdigest()
    ctx = EvidenceContext(family + '_presentation', scope, fingerprint, 'accepted-view-v1', league_id)
    evidence = tuple(EvidenceItem(key, label, kind, ctx, key, unit,
        state or (A.UNAVAILABLE if value is None else A.AVAILABLE), None if value is None else str(value))
        for key, label, value, unit, kind, state in rows)
    return Explanation(subject, league_id, (ctx,), evidence,
        Statement(conclusion[0], conclusion[1], (rows[0][0],)),
        limitations=tuple(Statement(code, text, (key,)) for code, text, key in limits),
        advanced=tuple(Statement(code, text, (key,)) for code, text, key in advanced))


def row(key, label, value, unit='classification', kind=K.DERIVED, state=None):
    return key, label, value, unit, kind, state


def player_projection_explanation(view):
    rows = [row('projection', f"Week {view['week']} Sleeper projection",
                view['display'] if view.get('value') is not None else None, 'fantasy points', K.SOURCE),
            row('confidence', 'Projection evidence confidence', view.get('confidence'), 'source evidence support')]
    limits = [('PROJECTION_UNAVAILABLE', view.get('reason') or 'No supported projection is available for this week.', 'projection')] if view.get('value') is None else []
    return _build('Projection context', 'projection', view.get('league_id'),
        f"player:{view['player_id']}/season:{view.get('season')}/week:{view['week']}/source:{view.get('generation')}", rows,
        ('WEEKLY_SOURCE_CONTEXT', 'League-scored weekly expectation, not dynasty value.'), limits=limits)


def player_profile_explanation(report, *, league_id):
    profile = report.profile
    rows = [row('identity', 'Player', profile.name, 'player identity', K.SOURCE),
            row('team', 'Current NFL team', profile.nfl_team, 'NFL team', K.SOURCE),
            row('age', 'Age / lifecycle input', profile.age, 'years', K.SOURCE),
            row('status', 'Reported availability/status', profile.injury_status, 'source status', K.SOURCE)]
    if report.core_values.market.score is not None:
        rows.append(row('market', 'Profile Market acquisition price', report.core_values.market.score,
                        f'normalized Market 0–{report.core_values.market.scale_maximum}'))
    if report.long_term_outlook:
        rows.append(row('longevity_context', 'Accepted long-term evidence context', report.long_term_outlook,
                        'scoped outlook', K.INTERPRETATION))
    if report.value_profile is not None:
        rows.append(row('roster_role', 'Current roster contribution role', report.value_profile.lineup.role,
                        'roster role'))
    # Consume accepted non-projection production facts only. Current-week
    # projection values remain exclusively in the dynamic weekly panel.
    for index, evidence in enumerate(report.core_values.redraft.evidence):
        if evidence.factor in ('Season Average', 'Previous Season Average', 'Targets per game', 'Carries per game'):
            rows.append(row(f'production.{index}', evidence.factor,
                            evidence.observed_value if evidence.available else None,
                            {'Targets per game': 'targets/game', 'Carries per game': 'carries/game'}.get(evidence.factor, 'league-scored fantasy points/game')))
    return _build('Player evidence context', 'player', league_id, f'player:{profile.player_id}', rows,
        ('PLAYER_EVIDENCE_SCOPE', 'Market price, demonstrated production and weekly expectation answer different questions.'))


def market_explanation(detail, trend, *, league_id):
    asset = detail['asset']
    rows = [row('price', 'Current acquisition price', asset['values'].get('market_value'), 'normalized Market 0–1000')]
    incompatible = bool(trend.get('comparison_reasons')) or trend.get('direction') == 'not_comparable'
    direction = trend.get('direction')
    comparable = not incompatible and direction in ('rising', 'falling', 'stable', 'volatile')
    rows.append(row('trend', 'Observed Market trend', direction if comparable else None,
                    state=A.AVAILABLE if comparable else A.NO_COMPARABLE_EVIDENCE))
    rows.append(row('as_of', 'Trend observation boundary', trend.get('as_of'), 'as-of timestamp'))
    rows.append(row('confidence', 'Trend evidence confidence', trend.get('confidence'), 'evidence support'))
    for index, provider in enumerate(detail.get('providers') or []):
        if isinstance(provider, str):
            rows.append(row(f'provider.{index}', 'Participating provider', provider, 'provider identity', K.SOURCE))
        elif isinstance(provider, dict):
            for field, label in (('provider', 'Participating provider'), ('market_format', 'Provider format'),
                                 ('source_updated_at', 'Provider update time'), ('retrieved_at', 'Retrieval time')):
                if provider.get(field) is not None:
                    rows.append(row(f'provider.{index}.{field}', label, provider[field], 'provider metadata', K.SOURCE))
    # Never promote generic rank or result-list position into a global rank.
    limits = []
    if rows[0][2] is None:
        limits.append(('MARKET_UNAVAILABLE', 'Current acquisition-price evidence is unavailable, not zero.', 'price'))
    if not comparable:
        limits.append(('MARKET_NOT_COMPARABLE' if incompatible else 'MARKET_HISTORY_INSUFFICIENT',
            'Historical observations cannot support a comparable trend.' if incompatible else 'There is not enough comparable history to describe movement.', 'trend'))
    boundary_text = {
        'METHODOLOGY_VERSION_CHANGED': 'DTOS methodology changed. This boundary is not a player price surge or decline.',
        'COMPARABLE_HISTORY_UNAVAILABLE': 'Required comparison identity or history is unavailable; missing coverage is not stable performance.',
        'INCOMPATIBLE_OBSERVATION_BOUNDARY': 'Provider, format, scale or observation context is incompatible across this boundary; no numeric movement is claimed.',
    }
    for code in dict.fromkeys(trend.get('comparison_reasons') or ()):
        if code in boundary_text:
            limits.append((code, boundary_text[code], 'trend'))
    return _build('Market evidence explained', 'market', league_id,
        f"asset:{asset['asset_id']}/generation:{detail.get('market_generation')}/method:{trend.get('method_version')}", rows,
        ('MARKET_PRICE_SCOPE', 'Market price describes acquisition-price evidence, not intrinsic player worth.'), limits=limits,
        advanced=[('MOVEMENT_NOT_CAUSE', 'An observed trend does not by itself establish why the price changed.', 'trend')] if comparable else [])


def pick_explanation(pick, market, *, league_id):
    if pick.get('league_id') not in (None, league_id):
        raise ValueError('Pick explanation league mismatch')
    quote = market.get('quote') or {}
    rows = [row('year', 'Draft year', pick.get('year', pick.get('season')), 'year', K.SOURCE),
            row('round', 'Round', pick.get('round'), 'round', K.SOURCE),
            row('original', 'Original franchise', pick.get('original_roster_id'), 'franchise identity', K.SOURCE),
            row('owner', 'Current owner', pick.get('current_owner_id', pick.get('owner_id')), 'franchise identity', K.SOURCE),
            row('price', 'Pick acquisition price', market.get('normalized_market_price'), 'normalized Market 0–1000'),
            row('quote', 'Market quote concept', quote.get('pick_type'), 'quoted asset concept', K.SOURCE),
            row('provider', 'Market provider', quote.get('provider'), 'provider identity', K.SOURCE),
            row('range', 'Original-franchise projected range', pick.get('projected_range')),
            row('confidence', 'Range confidence, not pick quality', pick.get('projected_range_confidence')),
            row('slot', 'Established exact slot', pick.get('exact_slot') if pick.get('exact_slot_established') is True else None, 'draft slot')]
    limits = []
    if market.get('normalized_market_price') is None:
        limits.append(('PICK_MARKET_UNAVAILABLE', 'No supported current Pick Market price is available; no legacy score is substituted.', 'price'))
    if pick.get('projected_range') == 'UNKNOWN':
        limits.append(('PICK_RANGE_UNKNOWN', 'Available evidence does not establish an Early/Mid/Late range.', 'range'))
    return _build('Pick evidence explained', 'pick', league_id,
        f"{rows[0][2]}/{pick.get('round')}/{pick.get('original_roster_id')}/range:{pick.get('range_generation')}/market:{market.get('normalization_generation')}", rows,
        ('PICK_IDENTITY_SCOPE', 'Range follows the original franchise; trading the pick changes its owner, not its origin.'), limits=limits,
        advanced=[('RANGE_CONFIDENCE_SCOPE', 'Range confidence measures uncertainty about the projected slot, not whether the pick is good or bad.', 'confidence'),
                  ('QUOTE_CONCEPT_SCOPE', 'A generic Market quote is not an Early/Mid/Late forecast.', 'quote')])


def pick_history_explanation(dossier, *, league_id):
    rows = [row('identity', 'Historical pick identity', dossier['pick_id'], 'pick identity', K.SOURCE),
            row('original', 'Original franchise', dossier.get('original_franchise_id'), 'franchise identity', K.SOURCE),
            row('chain', 'Retained ownership chain', ' → '.join(dossier.get('owner_chain') or []) or None,
                'chronological franchise identities', K.SOURCE),
            row('reconciliation', 'Historical reconciliation', dossier.get('reconciliation_status'))]
    limits = [('OWNERSHIP_CHAIN_GAP', 'The retained ownership chain has missing transfer links; it is not a complete history.', 'chain')] if dossier.get('ownership_chain_gaps') else []
    return _build('Pick history explained', 'pick_history', league_id, dossier['pick_id'], rows,
        ('HISTORICAL_OWNERSHIP', 'Historical transfers remain historical; a return to an earlier owner is retained.'), limits=limits)
