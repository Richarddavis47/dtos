"""Shared presentation envelope over existing Attention evidence, not an engine."""
from dataclasses import dataclass
from typing import Mapping, Any


@dataclass(frozen=True)
class EventPresentation:
    identity: str
    league_id: str
    entity: str
    family: str
    kind: str
    reference: str
    generation: str
    methodology: str
    current: Mapping[str, Any]
    prior: Mapping[str, Any] | None
    comparability: str
    as_of: str
    clock_semantic: str
    materiality_reason: str
    confidence: str
    title: str
    summary: str
    destination: str


def event_presentation(item, *, league_id, roster_id):
    """Normalize only already-qualified canonical adapter output."""
    if not item.get('qualifies') or item.get('kind') not in {'current_state', 'change_event'}:
        raise ValueError('Presentation requires a qualified state or change')
    if str(item.get('league_id', league_id)) != str(league_id):
        raise ValueError('Cross-league event')
    change = item['kind'] == 'change_event'
    if change and (not item.get('prior') or not item.get('current') or not item.get('observed_at')):
        raise ValueError('Change claims require retained prior/current evidence and boundary')
    if not item['href'].startswith('/') or item['href'].startswith('//'):
        raise ValueError('Event destination must be an internal product surface')
    return EventPresentation(item['identity'], str(league_id),
        item.get('reference') if change else f'roster:{roster_id}:week:{item["week"]}',
        item['family'], item['kind'], item['reference'], item['generation'], item['source_methodology'],
        item['current'] if change else {'unsupported_slots': tuple(item['unsupported_slots'])},
        item['prior'] if change else None, 'comparable' if change else 'not_applicable_current_state',
        item['observed_at'] if change else f'prepared-week:{item["week"]}',
        item.get('clock_semantic', 'pinned prepared league-week; no invented observation timestamp'),
        item['reason'], item['confidence'], item['title'], item['why'], item['href'])
