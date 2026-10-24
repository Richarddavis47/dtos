"""Ephemeral qualification of prepared manager facts; never regenerate history."""
from __future__ import annotations

from contextvars import ContextVar
from functools import wraps
from hashlib import sha256
import json
from typing import Any, Mapping

METHOD = 'current-manager-publication-1'
FIELDS = ('front_office_evidence', 'gm_behavioral_intelligence')
_preparation: ContextVar[tuple[object, str] | None] = ContextVar('manager_evidence_preparation', default=None)


def source_identity(data: Mapping[str, Any]) -> str:
    """Reuse bounded source fingerprints, without archive decoding or factories."""
    from src.core.gm_behavioral_intelligence.diagnostics import league_gm_observations
    source = (league_gm_observations.source_identity(data), data.get('league'),
        tuple((key, data.get(key)) for key in ('source_generation', 'source_generations',
            'history_generation', 'canonical_history_generation', 'season', 'week', 'fois_history')))
    return sha256(json.dumps(source, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def begin_preparation(data):
    return _preparation.set((data, source_identity(data)))


def end_preparation(token):
    _preparation.reset(token)


def preparing(function):
    @wraps(function)
    def wrapped(self, data, *args, **kwargs):
        prior = _preparation.get()
        token = None if prior is not None and prior[0] is data else begin_preparation(data)
        try:
            return function(self, data, *args, **kwargs)
        finally:
            if token is not None:
                end_preparation(token)
    return wrapped


def _identity(data, roster_id):
    from src.core.fois.identity import canonical_league_identity, identity_from_team
    matches = [row for row in data.get('teams') or ()
        if isinstance(row, Mapping) and str(row.get('roster_id')) == str(roster_id)]
    if len(matches) != 1:
        return None
    team = matches[0]
    owner = team.get('owner_id')
    alternate = team.get('user_id')
    if (isinstance(owner, bool) or isinstance(alternate, bool)
            or (owner not in (None, '') and alternate not in (None, '') and str(owner) != str(alternate))):
        return None
    identity = identity_from_team(canonical_league_identity(data.get('league') or {}), team)
    return identity if identity.owner_id and identity.owner_id != 'unassigned' else None


def compatible_row(data, field, roster_id, row):
    from src.core.front_office_evidence.models import FRONT_OFFICE_EVIDENCE_METHOD_VERSION
    from src.core.gm_behavioral_intelligence.models import GM_BEHAVIOR_METHOD_VERSION
    identity = _identity(data, roster_id)
    expected_method = {'front_office_evidence': FRONT_OFFICE_EVIDENCE_METHOD_VERSION,
                       'gm_behavioral_intelligence': GM_BEHAVIOR_METHOD_VERSION}.get(field)
    league = str((data.get('league') or {}).get('league_id') or '')
    if not isinstance(row, Mapping):
        return False
    count = row.get('transaction_count')
    return bool(isinstance(count, int) and not isinstance(count, bool) and count >= 0
        and identity and expected_method and row.get('league_id') == league
        and row.get('franchise_id') == identity.franchise_id and row.get('gm_id') == identity.gm_id
        and row.get('method_version') == expected_method and row.get('semantic_identity'))


def _row_binding(row):
    # Dimension/reference ordering is not an evidence change. Bind all values,
    # not just an unverified caller-supplied semantic-identity string.
    canonical = dict(row)
    if isinstance(canonical.get('dimensions'), list):
        canonical['dimensions'] = sorted(canonical['dimensions'], key=lambda x: str(x.get('key')) if isinstance(x, Mapping) else str(x))
    return {'semantic_identity': row.get('semantic_identity'), 'digest': sha256(
        json.dumps(canonical, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()}


def publish_rows(data, field, rows):
    """Seal products only inside their producer's pinned input scope.

    A listener cannot relabel an old result with a newly observed generation.
    Unbound legacy rows remain available to retained readers, never trusted as
    current-manager evidence. No persistent schema/grade is modified.
    """
    data[field] = rows
    pinned = _preparation.get()
    current = data.get('_manager_evidence_publication')
    current = current if isinstance(current, Mapping) else {}
    if pinned is None or pinned[0] is not data or source_identity(data) != pinned[1]:
        data.pop('_manager_evidence_publication', None)
        return
    source = pinned[1]
    bindings = dict(current.get('bindings') or {}) if current.get('source_identity') == source else {}
    bindings[field] = {str(key): _row_binding(row) for key, row in rows.items()
        if isinstance(row, Mapping) and compatible_row(data, field, key, row)}
    data['_manager_evidence_publication'] = {'method': METHOD, 'source_identity': source, 'bindings': bindings}


def admitted(data, field, roster_id, row, current_source):
    publication = data.get('_manager_evidence_publication')
    if not isinstance(publication, Mapping) or not isinstance(publication.get('bindings'), Mapping):
        return False
    if (publication.get('method') != METHOD or publication.get('source_identity') != current_source
            or not compatible_row(data, field, roster_id, row)):
        return False
    bound = (publication.get('bindings') or {}).get(field) or {}
    if not isinstance(bound, Mapping) or bound.get(str(roster_id)) != _row_binding(row):
        return False
    if field == 'front_office_evidence' and row.get('transaction_count'):
        generations = row.get('source_history_generations')
        if (not isinstance(generations, (tuple, list)) or not generations
                or any(not isinstance(x, str) or not x for x in generations)
                or not row.get('evidence_references')):
            return False
        declared = data.get('canonical_history_generation') or data.get('history_generation')
        if declared is not None:
            allowed = [declared] if isinstance(declared, str) else declared
            if (not isinstance(allowed, (tuple, list)) or not allowed
                    or any(not isinstance(x, str) or not x for x in allowed)
                    or not set(generations) <= set(allowed)):
                return False
    if field == 'gm_behavioral_intelligence':
        summaries = data.get('front_office_evidence')
        if not isinstance(summaries, Mapping):
            return False
        summary = summaries.get(str(roster_id)) or {}
        summary_binding = (publication.get('bindings') or {}).get('front_office_evidence') or {}
        if (not admitted(data, 'front_office_evidence', roster_id, summary, current_source)
                or summary_binding.get(str(roster_id)) != _row_binding(summary)
                or row.get('source_evidence_identity') != summary.get('semantic_identity')):
            return False
        if row.get('transaction_count') and not summary.get('source_history_generations'):
            return False
    return True


def consumer_identity(data):
    """Fence source and product transitions through final response publication."""
    products = {field: {str(key): _row_binding(row) for key, row in (data.get(field).items() if isinstance(data.get(field), Mapping) else ())
                       if isinstance(row, Mapping)} for field in FIELDS}
    return sha256(json.dumps((source_identity(data), data.get('_manager_evidence_publication'), products),
        sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()
