"""Small identity evidence join; no current-age inference or historical writes."""
from datetime import date, datetime


def birth_date_metadata(player: dict, previous: dict | None = None) -> dict[str, str]:
    """Omission cannot erase a supported date; disagreement cannot pick a winner."""
    dates = set()
    invalid = False
    retained_conflict = False
    nested = player.get('metadata')
    for evidence in (previous or {}, nested if isinstance(nested, dict) else {}, player):
        invalid |= evidence.get('birth_date_status') == 'invalid'
        retained_conflict |= evidence.get('birth_date_status') == 'conflicting'
        for key in ('birth_date', 'birthdate', 'birth_date_candidates'):
            for value in str(evidence.get(key) or '').split(','):
                if not value:
                    continue
                try:
                    dates.add(date.fromisoformat(value).isoformat())
                except ValueError:
                    try:
                        dates.add(datetime.fromisoformat(value.replace('Z', '+00:00')).date().isoformat())
                    except ValueError:
                        invalid = True
    result = {'birth_date_status': 'conflicting' if len(dates) > 1 or retained_conflict else
              'supported' if dates else 'invalid' if invalid else 'missing'}
    if dates:
        result['birth_date_candidates'] = ','.join(sorted(dates)[:2])
        result['birth_date_source'] = 'Sleeper player identity'
    if len(dates) == 1 and not retained_conflict:
        result['birth_date'] = next(iter(dates))
    return result


def historical_age(metadata: dict, decision_at: str | None):
    if metadata.get('birth_date_status') in {'conflicting', 'invalid', 'identity_mismatch'}:
        return None, None, (f"birth_date_{metadata['birth_date_status']}",)
    evidence = birth_date_metadata(metadata)
    status = evidence['birth_date_status']
    if status != 'supported':
        return None, evidence.get('birth_date'), (f'birth_date_{status}',)
    try:
        boundary = datetime.fromisoformat(str(decision_at).replace('Z', '+00:00'))
        born = date.fromisoformat(evidence['birth_date'])
        if born > boundary.date():
            return None, evidence['birth_date'], ('birth_date_after_decision',)
        return round((boundary.date() - born).days / 365.2425, 2), evidence['birth_date'], ()
    except (ValueError, TypeError):
        return None, evidence['birth_date'], ('age_decision_date_unavailable',)
