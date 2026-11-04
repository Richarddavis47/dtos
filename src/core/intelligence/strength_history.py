"""Bounded derived Team Strength transitions; canonical payloads stay referenced."""
import json

MAX_TRANSITIONS = 128


def record_strength_history(store, profile, *, observed_at):
    written = 0
    with store.connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        for roster, team in sorted(profile['teams'].items()):
            key = json.dumps([profile['league_id'], profile['season'], str(roster)], separators=(',', ':'))
            state = {
                'methodology': profile['methodology_version'],
                'current_week': profile['current_week'], 'next_n': profile['next_n'],
                'horizons': {name: {field: row.get(field) for field in (
                    'availability', 'weeks_requested', 'weeks_supported', 'total',
                    'supported_week_subtotal', 'source_confidence_range', 'league_rank')}
                    for name, row in team['horizons'].items()},
                'depth_bye': {str(week): {
                    'supported_reserve_slots': row['reserve_capacity']['supported_slots'],
                    'reserve_subtotal': row['reserve_capacity']['known_subtotal'],
                    'known_bye_count': len(row['known_bye_player_ids']),
                    'bye_coverage': row['bye_evidence_availability'],
                } for week, row in team['weekly'].items()},
            }
            row = connection.execute("SELECT value FROM metadata WHERE namespace='team_strength_history' AND key=?", (key,)).fetchone()
            prior = json.loads(row[0]) if row else {'events': [], 'discarded_transitions': 0}
            events = prior['events']
            previous = events[-1]['state'] if events else None
            if previous == state:
                continue
            reasons = ['INITIAL_OBSERVATION'] if previous is None else []
            if previous is not None:
                if previous['methodology'] != state['methodology']:
                    reasons = ['METHODOLOGY_CHANGED']
                else:
                    for field, reason in (('current_week', 'WEEK_ADVANCED'), ('next_n', 'HORIZON_CHANGED'),
                                          ('horizons', 'HORIZON_EVIDENCE_CHANGED'), ('depth_bye', 'DEPTH_BYE_EVIDENCE_CHANGED')):
                        if previous[field] != state[field]:
                            reasons.append(reason)
            events.append({'state': state, 'observed_at': observed_at, 'reasons': reasons,
                           'projection_generation': profile['projection_generation'],
                           'assessment_generation': profile['semantic_generation'],
                           'roster_reference': profile['roster_reference'],
                           'calendar_reference': profile['calendar_reference']})
            overflow = max(0, len(events) - MAX_TRANSITIONS)
            value = {'events': events[-MAX_TRANSITIONS:],
                     'discarded_transitions': prior['discarded_transitions'] + overflow}
            connection.execute("INSERT INTO metadata(namespace,key,value) VALUES('team_strength_history',?,?) "
                               "ON CONFLICT(namespace,key) DO UPDATE SET value=excluded.value,updated_at=CURRENT_TIMESTAMP",
                               (key, json.dumps(value, sort_keys=True, separators=(',', ':'))))
            written += 1
    return written
