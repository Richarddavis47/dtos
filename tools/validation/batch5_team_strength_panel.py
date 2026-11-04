"""Read-only source -> candidate background preparation; private derived report."""
import argparse
import asyncio
import json
import tempfile
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import httpx

from src.core.intelligence.season_calendar import season_calendar
from src.core.intelligence.team_strength import prepare_for_data, compatible_profile
from src.core.projection_intelligence.service import ProjectionService
from src.core.projection_intelligence.sleeper_provider import SleeperProjectionClient
from src.core.data_platform.global_evidence import GlobalEvidenceStore
from src.core.data_platform.schedule_ingestion import ingest_schedule
from src.core.data_platform.global_schedule import schedule_from_facts
from src.core.intelligence.orchestrator import IntelligenceOrchestrator
from src.core.intelligence.cache import IntelligenceCache


def schedule_facts(directory, season):
    store = GlobalEvidenceStore(Path(directory)/'global.sqlite3')
    observed = datetime.now(timezone.utc).isoformat()
    with httpx.Client(timeout=60) as client:
        provenance, _ = ingest_schedule(client, store, season=season, retrieved_at=observed,
                                        temporary_directory=Path(directory))
    return store.read('schedule', None, season=season, as_of=observed), provenance, observed


async def panel(ids, *, trades=False, trade_for=False, profile_search=False, shop=False, recommended=False, adjust=False, shop_performance=False, final_parity=False):
    report = {'observed_at': datetime.now(timezone.utc).isoformat(), 'leagues': []}
    parity_inputs = []
    async with httpx.AsyncClient(timeout=30) as client:
        market = None
        if trades or trade_for:
            from src.core.data_platform.provider_activation import refresh_public_market
            from src.core.valuation.normalization import prepare_market_normalization
            market = await refresh_public_market(client)
            prepare_market_normalization(market)
        leagues = [(await client.get('https://api.sleeper.app/v1/league/' + league_id)).json() for league_id in ids]
        calendars = [season_calendar(league) for league in leagues]
        if any(row['availability'] != 'supported' for row in calendars):
            raise ValueError('Real league calendar unsupported; do not default')
        feeds = {}
        schedules = {}
        for league, calendar in zip(leagues, calendars):
            season = int(league['season'])
            weeks = sorted(set(calendar['remaining_regular_season_weeks'] + [w for r in calendar['playoff_rounds'] for w in r]))
            for week in weeks:
                if (season, week) not in feeds:
                    feeds[(season, week)] = (await SleeperProjectionClient().fetch(client, season=season, week=week))[0]
            raw_rosters = (await client.get(f"https://api.sleeper.app/v1/league/{league['league_id']}/rosters")).json()
            catalog = {str(row['player_id']): row for (year, _), payload in feeds.items() if year == season for row in payload}
            teams = []
            for roster in raw_rosters:
                players = []
                for pid in roster.get('players') or []:
                    row = catalog.get(str(pid), {})
                    players.append({'id': str(pid), 'position': (row.get('player') or {}).get('position'),
                        'team': row.get('team'),
                        'roster_slot': 'Starter' if pid in (roster.get('starters') or []) else 'IR' if pid in (roster.get('reserve') or []) else 'Taxi' if pid in (roster.get('taxi') or []) else 'Bench'})
                teams.append({'roster_id': roster['roster_id'], 'players': players})
            data = {'league': league, 'week': calendar['current_week'], 'teams': teams,
                    'players': {p['id']: p for team in teams for p in team['players']}}
            with tempfile.TemporaryDirectory(prefix='dtos-strength-') as directory:
                if season not in schedules:
                    schedules[season] = await asyncio.to_thread(schedule_facts, directory, season)
                facts, schedule_provenance, schedule_observed = schedules[season]
                nfl_teams = {p.get('team') for p in data['players'].values() if p.get('team')}
                by_team = {team: schedule_from_facts(facts, team, season=season, as_of=schedule_observed)['bye_week'] for team in nfl_teams}
                byes = {pid: by_team[p['team']] for pid, p in data['players'].items() if by_team.get(p.get('team')) is not None}
                bye_evidence = {'season': season, 'player_weeks': byes,
                                'reference': hashlib.sha256(json.dumps(sorted(f['fingerprint'] for f in facts)).encode()).hexdigest()}
                service = ProjectionService(Path(directory) / 'projection.sqlite3')
                publication_start = time.perf_counter()
                service.publish_horizon({w: feeds[(season, w)] for w in weeks}, data=data,
                    league_id=league['league_id'], season=season, current_week=data['week'])
                publication_seconds = time.perf_counter() - publication_start
                start = time.perf_counter()
                timings = {}
                profile = prepare_for_data(service, data, timings=timings, bye_evidence=bye_evidence)
                duration = time.perf_counter() - start
                read_start = time.perf_counter()
                assert compatible_profile(data, service.snapshot()) is profile
                timings['prepared_read_seconds'] = time.perf_counter() - read_start
                timings['projection_publication_seconds'] = publication_seconds
                sizes_before = {suffix: Path(str(service._database_file) + suffix).stat().st_size if Path(str(service._database_file) + suffix).exists() else 0 for suffix in ('', '-wal', '-shm')}
                replay_start = time.perf_counter()
                again = prepare_for_data(service, data, bye_evidence=bye_evidence)
                timings['unchanged_preparation_seconds'] = time.perf_counter() - replay_start
                assert again == profile
                sizes_after = {suffix: Path(str(service._database_file) + suffix).stat().st_size if Path(str(service._database_file) + suffix).exists() else 0 for suffix in ('', '-wal', '-shm')}
                assert sizes_after == sizes_before
                active_consumers = {}
                with patch('src.core.projection_intelligence.projection_service.snapshot', side_effect=service.snapshot):
                    engine = IntelligenceOrchestrator(cache=IntelligenceCache())
                    for team in teams:
                        assessment = engine.analyze(data, team['roster_id']).team_assessment
                        evidence = assessment.multi_horizon_strength
                        assert evidence['generation'] == profile['semantic_generation']
                        assert assessment.team.competitive_window.production_profile == evidence
                        active_consumers[str(team['roster_id'])] = {'generation': evidence['generation'],
                            'team_hq_equals_competitive_window': True}
                trace_count = 0
                for week in weeks:
                    snapshot = service.week_snapshot(week, generation_snapshot=service.snapshot())
                    for team in profile['teams'].values():
                        for entry in team['weekly'][week]['optimal']['entries']:
                            assert entry['projected_points'] == snapshot['players'][entry['asset_id']]['canonical_projection']
                            trace_count += 1
                trade_panel = None
                if trades or trade_for:
                    from tools.validation.batch5_trade_samples import samples
                    response = await client.get(f"https://api.sleeper.app/v1/league/{league['league_id']}/traded_picks")
                    response.raise_for_status()
                    trade_panel = samples(data, service, market, response.json(), Path(directory), searches=trade_for, profile_search=profile_search, shop=shop, recommended=recommended, adjust=adjust, shop_performance=shop_performance)
                if final_parity:
                    from tools.validation.batch5_final_parity import RetainedRead
                    parity_inputs.append((data, RetainedRead(service, weeks)))
                report['leagues'].append({'league_id': league['league_id'], 'calendar': calendar,
                    'preparation_seconds': duration, 'timings': timings, 'replay_growth': {k: sizes_after[k] - sizes_before[k] for k in sizes_before},
                    'schedule_provenance': schedule_provenance,
                    'active_consumers': active_consumers, 'exact_player_week_traces': trace_count,
                    'trade_panel': trade_panel,
                    'profile': profile})
                print(json.dumps({'league': league['name'], 'teams': len(teams), 'seconds': duration,
                    'playoff_rounds': calendar['playoff_rounds'], 'incomplete': {rid: [w for w, row in team['weekly'].items() if not row['available']] for rid, team in profile['teams'].items()}}), flush=True)
    if final_parity:
        from tools.validation.batch5_final_parity import round_trip
        report['final_parity'] = round_trip(parity_inputs)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--league', action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--trades', action='store_true')
    parser.add_argument('--trade-for', action='store_true')
    parser.add_argument('--profile-search', action='store_true')
    parser.add_argument('--shop', action='store_true')
    parser.add_argument('--recommended', action='store_true')
    parser.add_argument('--adjust', action='store_true')
    parser.add_argument('--shop-performance', action='store_true')
    parser.add_argument('--final-parity', action='store_true')
    args = parser.parse_args()
    result = asyncio.run(panel(args.league, trades=args.trades or args.final_parity, trade_for=args.trade_for or args.shop or args.recommended or args.adjust or args.shop_performance, profile_search=args.profile_search, shop=args.shop, recommended=args.recommended, adjust=args.adjust, shop_performance=args.shop_performance, final_parity=args.final_parity))
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
