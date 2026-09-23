"""Read existing bounded pick history without initialization, writes or scans."""
from datetime import datetime, timezone, timedelta
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3


def instant(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except ValueError:
        return None


def pick_changes(data, roster_id, path, *, now=None):
    now = now or datetime.now(timezone.utc)
    league = str((data.get('league') or {}).get('league_id') or '')
    rows = []
    path = Path(path)
    if not path.is_file():
        return rows, 'history_unavailable'
    # Canonical ledger rows inherit the admitted data container's league.
    # Reject explicit conflicts; do not require an invented per-row field.
    owned = [p for p in data.get('pick_ledger') or []
             if str(p.get('current_owner_id')) == str(roster_id)
             and str(p.get('league_id', league)) == league]
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as connection:
            for pick in owned:
                key = json.dumps([league, pick.get('year', pick.get('season')), pick.get('round'), pick.get('original_roster_id')], separators=(',', ':'))
                retained = connection.execute("SELECT value FROM metadata WHERE namespace='pick_range_history' AND key=?", (key,)).fetchone()
                if not retained:
                    continue
                events = json.loads(retained[0]).get('events') or []
                if len(events) < 2:
                    continue
                before, after = events[-2:]
                old, new = before['state'], after['state']
                observed, prior = instant(after.get('observed_at')), instant(before.get('observed_at'))
                current = {k: pick.get(k) for k in ('projected_range', 'projected_range_confidence', 'range_method')}
                current['exact_slot'] = pick.get('exact_slot') if pick.get('exact_slot_established') is True else None
                reason = None
                if any(state.get('projected_range') not in {'EARLY', 'MID', 'LATE', 'UNKNOWN'} for state in (old, new)):
                    reason = 'UNSUPPORTED_RANGE_STATE'
                elif not new.get('range_method') or old.get('range_method') != new.get('range_method') or 'METHODOLOGY_CHANGED' in after.get('reasons', []):
                    reason = 'METHODOLOGY_BOUNDARY'
                elif new != current:
                    reason = 'CURRENT_STATE_MISMATCH'
                elif not observed or not prior or not prior < observed <= now:
                    reason = 'INVALID_TIME_BOUNDARY'
                elif observed < now - timedelta(days=7):
                    reason = 'OUTSIDE_RECENT_WINDOW'
                changed = old.get('projected_range') != new.get('projected_range')
                exact = new.get('exact_slot') is not None and old.get('exact_slot') != new.get('exact_slot')
                if not reason and not (changed or exact):
                    reason = 'CONFIDENCE_ONLY_NOT_MATERIAL'
                identity = hashlib.sha256((key + json.dumps([before, after], sort_keys=True)).encode()).hexdigest()
                coverage = 'UNKNOWN' in (old.get('projected_range'), new.get('projected_range'))
                code = 'EXACT_SLOT_ESTABLISHED' if exact else 'PICK_RANGE_COVERAGE_CHANGED' if coverage else 'PICK_RANGE_CHANGED'
                rows.append({'identity': identity, 'family': 'pick_change', 'kind': 'change_event',
                    'qualifies': reason is None, 'reason': reason or code, 'league_id': league,
                    'original_franchise': pick.get('original_roster_id'), 'current_owner': roster_id,
                    'prior': old, 'current': new, 'observed_at': after.get('observed_at'),
                    'clock_semantic': 'canonical range observation; not provider price update',
                    'generation': identity, 'source_methodology': new.get('range_method') or 'unavailable',
                    'reference': 'pick_range_history/' + key, 'href': '/picks',
                    'priority_reasons': ['OWNED_CAPITAL', 'EXACT_SLOT' if exact else 'RANGE_COVERAGE' if coverage else 'RANGE_CATEGORY', 'RECENT_OBSERVATION'],
                    'title': f"{pick.get('year', pick.get('season'))} round {pick.get('round')}: pick evidence changed",
                    'why': (f"Exact slot established: {new.get('exact_slot')}." if exact else
                            f"Projected range: {old.get('projected_range')} → {new.get('projected_range')}. "
                            + ('Evidence coverage changed; this is not a value gain or loss.' if coverage else 'Projected range is not a locked draft slot.')),
                    'confidence': f"Range confidence: {new.get('projected_range_confidence')}. Not an outcome probability."})
    except (sqlite3.Error, ValueError, KeyError, TypeError):
        return [], 'history_unreadable'
    return rows, 'available' if rows else 'no_comparable_retained_pair'
