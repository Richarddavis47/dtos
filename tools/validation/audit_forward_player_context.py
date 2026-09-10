"""Bounded public-source diagnostic: current metadata + canonical weekly feed."""
import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import httpx

from services.player_evidence import REFERENCE_SCORING_SETTINGS
from src.core.projection_intelligence.sleeper_provider import SleeperProjectionClient, parse_projection_feed
from src.core.valuation.forward_evidence import ForwardEvidence, assess_forward_context
from src.core.valuation.player_methodology import REFERENCE_SCORING


async def collect(ids):
    async with httpx.AsyncClient(timeout=45) as client:
        state_response = await client.get('https://api.sleeper.app/v1/state/nfl')
        state_response.raise_for_status()
        state = state_response.json()
        season, week = int(state['season']), int(state['week'])
        metadata = await client.get('https://api.sleeper.app/v1/players/nfl')
        metadata.raise_for_status()
        catalog = metadata.json()
        payload, _, _ = await SleeperProjectionClient().fetch(client, season=season, week=week)
        projections, fingerprint, counts = parse_projection_feed(payload,
            season=season, week=week, scoring=REFERENCE_SCORING_SETTINGS)
    if counts['duplicates'] or counts['malformed']:
        raise ValueError('Projection schema ambiguity requires review.')
    observed = datetime.now(timezone.utc)
    rows = []
    for player_id in ids:
        player = catalog.get(player_id) or {}
        projection = projections.get(player_id) or {}
        state = {key: player.get(key) for key in ('team', 'status', 'injury_status', 'depth_chart_order')}
        generation = hashlib.sha256(json.dumps([player_id, state, fingerprint], sort_keys=True).encode()).hexdigest()
        evidence = ForwardEvidence(player_id, observed.isoformat(), (observed + timedelta(hours=24)).isoformat(),
            generation, team=state['team'], status=state['status'], injury_designation=state['injury_status'],
            depth_order=state['depth_chart_order'], projection_player_id=projection.get('player_id'),
            projection_season=projection.get('season'), projection_week=projection.get('week'),
            projected_points=projection.get('league_projection'), projection_reference=REFERENCE_SCORING,
            projection_row_present=player_id in projections,
            projection_stats_present=bool(projection.get('projected_stats')),
            projection_applicable=None)
        rows.append({'name': player.get('full_name'), 'evidence': asdict(evidence),
            'assessment': assess_forward_context(evidence, player_id=player_id, season=season, week=week,
                as_of=observed.isoformat())})
    return {'season': season, 'week': week, 'observed_at': observed.isoformat(), 'players': rows,
        'limitations': ['24-hour diagnostic validity only; not a change to production freshness policy.',
            'Metadata retrieval does not independently prove each source field was recently updated.',
            'No contractual commitment, injury recovery, snap share or season-long expectation inferred.']}


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[2] / '.validation'
    destination = root / 'batch3-forward-context-v2.json'
    if not destination.exists():
        market = json.loads((root / 'batch3-panel-market.json').read_text(encoding='utf-8'))
        report = asyncio.run(collect([row['player_id'] for row in market['players']]))
        destination.write_text(json.dumps(report, sort_keys=True), encoding='utf-8')
    report = json.loads(destination.read_text(encoding='utf-8'))
    print(json.dumps({'season': report['season'], 'week': report['week'], 'players': len(report['players']),
        'with_weekly_projection': sum(row['assessment']['weekly_reference_projection'] is not None for row in report['players'])}))
