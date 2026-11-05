"""Bounded acquisition metadata for the existing current-season source cache.

No provider store, inferred empty buckets, or projection/valuation computation.
"""
import asyncio

SCHEMA = 'sleeper-transaction-periods-v1'


def compatible(data, league_id, season):
    league = data.get('league') or {}
    return (str(league.get('league_id')) == str(league_id)
            and str(league.get('season')) == str(season)
            and str(data.get('season', season)) == str(season))


def admitted_metadata(data, league_id, season):
    meta = data.get('transaction_acquisition')
    if (not isinstance(meta, dict) or meta.get('schema') != SCHEMA
            or str(meta.get('league_id')) != str(league_id)
            or str(meta.get('season')) != str(season)):
        return {}
    from .timestamps import canonical_utc_timestamp
    def timestamp(value):
        return canonical_utc_timestamp(value) if isinstance(value,str) and len(value)<=64 else None
    source = meta.get('periods')
    source = source if isinstance(source,dict) else {}
    periods = {}
    for week in range(19):
        row = source.get(str(week))
        if not isinstance(row,dict) or row.get('state') not in {
                'observed','observed_empty','unavailable','failed','malformed'}:
            continue
        periods[str(week)] = {'state': row['state'],
            'retrieved_at': timestamp(row.get('retrieved_at')),
            'last_attempt_at': timestamp(row.get('last_attempt_at')),
            'retained_last_valid': row.get('retained_last_valid') is True}
    through = meta.get('through_week')
    return {'schema': SCHEMA, 'league_id': str(league_id), 'season': str(season),
            'through_week': through if type(through) is int and 0<=through<=18 else None,
            'periods': periods}


def record_period(metadata, week, rows, *, observed_at, state=None, retained=False):
    """Copy at most19small observations, never the player/transaction universe."""
    source = metadata.get('periods') or {}
    source = source if isinstance(source,dict) else {}
    periods = {str(w):source[str(w)] for w in range(19) if str(w) in source}
    previous = periods.get(str(week)) or {}
    previous = previous if isinstance(previous,dict) else {}
    readable = isinstance(rows, list) and all(isinstance(r, dict) for r in rows)
    observed = state is None and readable
    periods[str(week)] = {
        'state': ('observed' if rows else 'observed_empty') if observed else state or ('unavailable' if rows is None else 'malformed'),
        'last_attempt_at': observed_at,
        'retrieved_at': observed_at if observed else previous.get('retrieved_at') if retained else None,
        'retained_last_valid': bool(retained),
    }
    return {**metadata, 'periods': {k:v for k,v in periods.items()
            if str(k).isdigit() and 0 <= int(k) <= 18}}


def current_period_metadata(data, week, rows, observed_at):
    if type(week) is not int or not 0 <= week <= 18:
        raise ValueError('Unsupported source transaction period')
    league = data.get('league') or {}
    meta = admitted_metadata(data, league.get('league_id'), league.get('season'))
    meta = {**meta, 'schema': SCHEMA, 'league_id': str(league.get('league_id')),
            'season': str(league.get('season')), 'through_week': int(week)}
    return record_period(meta, week, rows, observed_at=observed_at)


async def acquire_previous_periods(league, week, current_rows, previous, fetch, *, observed_at):
    """Same existing0..weeksource requests; retain valid failures explicitly."""
    if type(week) is not int or not 0 <= week <= 18:
        raise ValueError('Unsupported source transaction period')
    league_id, season = str(league['league_id']), str(league['season'])
    previous = previous if compatible(previous, league_id, season) else {}
    old_buckets = previous.get('season_transactions') or {}
    old_buckets = old_buckets if isinstance(old_buckets, dict) else {}
    meta = {**admitted_metadata(previous,league_id,season), 'schema': SCHEMA,
            'league_id': league_id, 'season': season, 'through_week': week}
    def stamp():
        return observed_at() if callable(observed_at) else observed_at
    buckets = {str(week): current_rows}
    meta = record_period(meta, week, current_rows, observed_at=stamp())

    async def get(period):
        try:
            rows = await fetch(f'/league/{league_id}/transactions/{period}')
            if rows is None:
                return period,None,'unavailable',stamp()
            if not isinstance(rows,list) or any(not isinstance(row,dict) for row in rows):
                return period,None,'malformed',stamp()
            return period,rows,None,stamp()
        except Exception:
            return period,None,'failed',stamp()  # Never retain provider exception strings.

    for period,rows,state,at in await asyncio.gather(*(get(w) for w in range(week))):
        old = old_buckets.get(str(period))
        retained = (state is not None and isinstance(old,list)
                    and all(isinstance(row,dict) for row in old))
        buckets[str(period)] = old if retained else rows
        meta = record_period(meta,period,buckets[str(period)],observed_at=at,
                             state=state,retained=retained)
    return buckets,meta
