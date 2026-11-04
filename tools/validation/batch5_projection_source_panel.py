"""Bounded read-only live source panel. No production application access/writes.

Reports source-stat scoring equivalence, not an unverified Sleeper UI claim.
Raw source payloads are not persisted; output is a compact diagnostic report.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx

from src.core.projection_intelligence.sleeper_provider import SleeperProjectionClient, parse_projection_feed, freshness_state
from src.core.projection_intelligence.service import ProjectionService
from src.core.trade_intelligence.lineup import optimal_legal_lineup
from src.core.projection_intelligence.scoring import scoring_coefficient


async def panel(league_ids, weeks, season):
    result = {'observed_at': datetime.now(timezone.utc).isoformat(), 'season': season,
              'weeks_sampled': weeks, 'source': 'Sleeper projection endpoint',
              'display_equivalence': 'NOT YET VERIFIED AGAINST SLEEPER LEAGUE UI', 'leagues': []}
    async with httpx.AsyncClient(timeout=30) as client:
        source = SleeperProjectionClient()
        feeds = {}
        for week in weeks:
            payload, _, _ = await source.fetch(client, season=season, week=week)
            feeds[week] = payload
        for league_id in league_ids:
            league_response = await client.get(f'https://api.sleeper.app/v1/league/{league_id}')
            roster_response = await client.get(f'https://api.sleeper.app/v1/league/{league_id}/rosters')
            league_response.raise_for_status()
            roster_response.raise_for_status()
            league = league_response.json()
            scoring = league['scoring_settings']
            scope = hashlib.sha256(json.dumps(scoring, sort_keys=True).encode()).hexdigest()
            group = {'league': league['name'], 'league_id': league_id, 'scoring_identity': scope,
                     'slots': league['roster_positions'], 'weeks': []}
            for week, payload in feeds.items():
                rows, fingerprint, normalization = parse_projection_feed(payload, season=season, week=week, scoring=scoring)
                raw = {str(item['player_id']): item for item in payload}
                week_result = {'week': week, 'source_fingerprint': fingerprint,
                               'normalization': normalization, 'player_examples': [], 'teams': [],
                               'source_stat_mismatches': []}
                for position in ('QB', 'RB', 'WR', 'TE'):
                    candidates = [row for row in rows.values() if row['position'] == position and row['league_projection'] is not None]
                    if not candidates:
                        continue
                    row = max(candidates, key=lambda item: item['league_projection'])
                    stats = raw[row['player_id']]['stats']
                    expected = float(sum((Decimal(str(stats.get(key) or 0)) * scoring_coefficient(weight)
                                          for key, weight in scoring.items()), Decimal(0)))
                    canonical = ProjectionService._canonical_projection(
                        {'id': row['player_id'], 'position': position}, row, season=season, week=week,
                        scoring_profile_id=scope, sleeper_freshness=freshness_state(row['source_updated_at']),
                        evidence_fingerprint=fingerprint, scoring_settings=scoring)
                    if canonical['canonical_projection'] != expected:
                        week_result['source_stat_mismatches'].append(row['player_id'])
                    metadata = raw[row['player_id']].get('player') or {}
                    week_result['player_examples'].append({
                        'player_id': row['player_id'], 'name': f"{metadata.get('first_name', '')} {metadata.get('last_name', '')}",
                        'position': position, 'source_default_ppr': row['displayed_projection'],
                        'source_stats_scored_independently': expected,
                        'canonical_league_points': canonical['canonical_projection'],
                        'source_updated_at': row['source_updated_at'], 'source_company': row['source_company']})
                for roster in roster_response.json():
                    excluded = set(roster.get('reserve') or []) | set(roster.get('taxi') or [])
                    players = [{'id': pid, 'position': rows.get(pid, {}).get('position'),
                                'projected_points': rows.get(pid, {}).get('league_projection'),
                                'lineup_eligible': pid not in excluded}
                               for pid in roster['players']]
                    lineup = optimal_legal_lineup(players, league['roster_positions'], week=week)
                    week_result['teams'].append({'roster_id': roster['roster_id'],
                        'available': lineup.available, 'total': lineup.projected_points,
                        'known_starters_subtotal': lineup.known_starters_subtotal,
                        'unsupported_slots': lineup.unsupported_slots, 'missing_players': len(lineup.missing_player_ids),
                        'actual_starters': roster.get('starters'),
                        'optimal': [vars(entry) for entry in lineup.entries]})
                week_result['supported_players'] = sum(row['league_projection'] is not None for row in rows.values())
                week_result['missing_players'] = sum(row['league_projection'] is None for row in rows.values())
                week_result['source_zero_count'] = sum(row['league_projection'] == 0 for row in rows.values())
                group['weeks'].append(week_result)
            result['leagues'].append(group)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--league', action='append', required=True)
    parser.add_argument('--week', type=int, action='append', required=True)
    parser.add_argument('--season', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = asyncio.run(panel(args.league, args.week, args.season))
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    for league in report['leagues']:
        for week in league['weeks']:
            print(json.dumps({'league': league['league'], 'week': week['week'],
                              'supported': week['supported_players'], 'missing': week['missing_players'],
                              'zeros': week['source_zero_count'], 'mismatches': week['source_stat_mismatches'],
                              'complete_lineups': sum(team['available'] for team in week['teams']),
                              'examples': week['player_examples']}))
