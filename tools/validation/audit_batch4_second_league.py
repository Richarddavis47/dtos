"""Bounded public-source second-league active Results/decision/tenure proof.

Does not export production or imply complete decision coverage. The 2025 draft
and three explicit transaction weeks are the representative decision sample.
"""
import asyncio
from dataclasses import asdict
import json
import os
from pathlib import Path

import httpx


async def main():
    retained = Path('.validation/batch4-assessment-transfer/replay.sqlite3').resolve()
    if not retained.is_file():
        raise RuntimeError('Authorized production-equivalent evidence has been cleaned up; do not silently substitute an empty store or re-export.')
    root = Path('.validation/batch4-second-league').resolve()
    root.mkdir(parents=True, exist_ok=True)
    for key, value in {
        'DTOS_HISTORY_STORAGE_ROOT': root, 'DTOS_DURABLE_HISTORY_REQUIRED': 'false',
        'DTOS_CACHE_FILE': root / 'cache.json',
        # Reuse the verified shared evidence; league-scoped checkpoint queries
        # must not admit Day Traders' private history into the second league.
        'DTOS_INTELLIGENCE_CHECKPOINT_FILE': Path('.validation/batch4-assessment-transfer/replay.sqlite3').resolve(),
        'DTOS_METADATA_DB_FILE': root / 'metadata.sqlite3',
        'DTOS_SLEEPER_SEASON_CACHE_ROOT': root / 'seasons',
    }.items():
        os.environ[key] = str(value)
    from src.core.history_context.store import canonical_history_store, sleeper_season_cache
    from src.core.fois.history import load_results_history
    from src.core.fois.service import FOISService
    from src.core.fois.repository import FOISRepository
    league_id = '1313063672284721152'
    season_ids = {2022: '801507209098944512', 2023: '916480972491722752',
                  2024: '1048395144501858304', 2025: '1180088889229967360'}
    names, provenance = {}, {}
    async with httpx.AsyncClient(timeout=30) as client:
        for year, source_id in season_ids.items():
            cached = sleeper_season_cache.read(league_id, year)
            if cached is None:
                suffixes = {'league': '', 'users': '/users', 'rosters': '/rosters',
                            'winners_bracket': '/winners_bracket', 'losers_bracket': '/losers_bracket'}
                async def read(suffix):
                    response = await client.get('https://api.sleeper.app/v1/league/' + source_id + suffix)
                    response.raise_for_status()
                    return response.json()
                values = await asyncio.gather(*(read(s) for s in suffixes.values()))
                facts = dict(zip(suffixes, values))
                if str(facts['league']['league_id']) != source_id or int(facts['league']['season']) != year:
                    raise ValueError('Source season/league mismatch')
                cached = sleeper_season_cache.normalize(league_id, year, facts)
                sleeper_season_cache.write(cached)
            names.update({str(u['user_id']): u.get('display_name') for u in cached.facts['users']})
            provenance[year] = {'source_league': source_id, 'checksum': cached.checksum,
                                'draft_rounds': cached.facts['league']['settings'].get('draft_rounds'),
                                'playoff_teams': cached.facts['league']['settings'].get('playoff_teams')}
        # One completed season, three explicit transaction weeks and its draft:
        # representative decision proof, not a claim of full historical counts.
        year = 2025
        cached = sleeper_season_cache.read(league_id, year)
        if 'transactions' not in cached.facts:
            async def sample_read(suffix):
                response = await client.get('https://api.sleeper.app/v1/league/' + season_ids[year] + suffix)
                response.raise_for_status()
                return response.json()
            transactions = {str(week): await sample_read('/transactions/' + str(week)) for week in (0, 1, 2)}
            drafts = await sample_read('/drafts')
            selections = []
            for draft in drafts:
                response = await client.get('https://api.sleeper.app/v1/draft/' + draft['draft_id'] + '/picks')
                response.raise_for_status()
                selections.extend({**pick, 'draft_id': draft['draft_id']} for pick in response.json())
            cached = sleeper_season_cache.normalize(league_id, year, {
                **cached.facts, 'transactions': transactions, 'drafts': drafts, 'draft_picks': selections})
            sleeper_season_cache.write(cached)
        elif isinstance(cached.facts.get('draft_picks'), dict):
            # Repair only this diagnostic cache's initial envelope shape.
            selections = [{**pick, 'draft_id': draft_id}
                          for draft_id, picks in cached.facts['draft_picks'].items() for pick in picks]
            cached = sleeper_season_cache.normalize(league_id, year, {**cached.facts, 'draft_picks': selections})
            sleeper_season_cache.write(cached)
        provenance[year]['checksum'] = cached.checksum
        provenance[year]['decision_sample_weeks'] = [0, 1, 2]
    histories = load_results_history(canonical_history_store, league_id)
    teams = []
    for roster, history in histories.items():
        seen = set()
        for season, owner in sorted(history.get('owner_by_season', {}).items()):
            if owner and owner not in seen:
                teams.append({'roster_id': int(roster), 'owner_id': owner,
                              'owner': names.get(owner, owner), 'players': []})
                seen.add(owner)
    scores = FOISService(FOISRepository(root / 'fois.sqlite3'))._generate_sync({
        'league': {'league_id': league_id, 'season': '2026'},
        'teams': teams, 'fois_history': histories,
    })
    output = {'scope': 'public source Results plus 2025 weeks 0/1/2 and draft; shared retained Market subset, NOT exhaustive production coverage',
              'unconnected_families': ['unsampled transactions', 'historical roster quality beyond available anchors'],
              'league': league_id, 'provenance': provenance,
              'managers': [{
                  'owner': s.gm_name, 'owner_id': s.owner_id, 'franchise_id': s.franchise_id,
                  'seasons': s.seasons_evaluated, 'model': s.model_version,
                  'overall': s.overall_score,
                  'results': asdict(next(c for c in s.category_scores if c.category_key == 'results')),
                  'decision_categories_available': [c.category_key for c in s.category_scores
                                                    if c.category_key != 'results' and c.normalized_score is not None],
                  'decision_categories': [asdict(c) for c in s.category_scores if c.category_key != 'results'],
              } for s in scores]}
    if any(s.league_id != league_id or not s.franchise_id.startswith(league_id + ':') for s in scores):
        raise ValueError('Cross-league identity')
    for score in scores:
        roster = score.franchise_id.rsplit(':', 1)[-1]
        sampled_owner = histories[roster].get('owner_by_season', {}).get('2025')
        if sampled_owner is None:
            sampled_owner = histories[roster].get('owner_by_season', {}).get(2025)
        if score.owner_id != sampled_owner:
            if any((c.details or {}).get('activity', 0) for c in score.category_scores):
                raise ValueError('Prior manager inherited 2025 decisions')
    output['isolation_checks'] = {
        'all_scores_in_second_league_namespace': True,
        'prior_managers_did_not_inherit_2025_decisions': True,
        'day_traders_private_history_not_supplied': True,
        'same_active_model': sorted({s.model_version for s in scores}),
        'limitations': 'Seasonal ownership evidence; no invented intra-season transfer timing.',
    }
    target = Path('docs/BATCH4_SECOND_LEAGUE_ACTIVE_PANEL.json')
    target.write_text(json.dumps(output, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'managers': len(scores), 'panel': str(target), 'scope': output['scope']}))


if __name__ == '__main__':
    asyncio.run(main())
