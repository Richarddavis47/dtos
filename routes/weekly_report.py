"""Prepared weekly report navigation. No provider calls or full analysis."""
import asyncio
from fastapi import APIRouter, Query

from config import SLEEPER_SEASON_CACHE_ROOT
from src.core.history_context.season_cache import SleeperSeasonCache
from services.matchup_season import prepare_season_matchups
from services.weekly_report import weekly_facts
from services.weekly_report_stories import compose_report
from src.ui.weekly_report import render_report


def create_weekly_report_router(*, require_data, page, cache=None):
    router = APIRouter(tags=['weekly-report'])
    archive = cache if cache is not None else SleeperSeasonCache(SLEEPER_SEASON_CACHE_ROOT)

    @router.get('/reports/weekly')
    async def report_page(season: int | None = Query(None, ge=2000, le=2100),
                          week: int | None = Query(None, ge=1, le=18)):
        active = require_data()
        league = active.get('league') or {}
        root_id = str(league.get('league_id') or '')
        active_season = int(league.get('season') or 0)
        target_season = season if season is not None else active_season
        target_week = week if week is not None else int(active.get('week') or 1)
        retained = None
        data = active
        if target_season != active_season:
            retained = await asyncio.to_thread(archive.read, root_id, target_season)
            if retained is None:
                return page('Weekly League Report', render_report(None, league.get('name', ''), target_season, target_week))
            source = retained.facts
            old_league = source.get('league') or {}
            if retained.league_id != root_id or str(old_league.get('season')) != str(target_season):
                return page('Weekly League Report', render_report(None, league.get('name', ''), target_season, target_week))
            async def read_section(path):
                parts = path.split('/')
                return ((source.get('matchups') or {}).get(parts[-1])
                        if parts[-2] == 'matchups' else source.get(parts[-1]))
            current = int((old_league.get('settings') or {}).get('leg') or 1)
            prepared = await prepare_season_matchups(old_league, current,
                (source.get('matchups') or {}).get(str(current)), read_section,
                observed_at='retained source')
            data = {'league': old_league, 'week': current, 'season_matchups': prepared,
                    'teams': [{'roster_id': r['roster_id'], 'team_name': f"Franchise {r['roster_id']}"}
                              for r in source.get('rosters') or []]}
        facts = weekly_facts(data, target_week, cached_season=retained)
        report = compose_report(facts)
        # Historical source-league IDs differ from active successor league IDs.
        # Never send a historical story to a current-season matchup detail.
        for story in report['stories']:
            if target_season != active_season:
                story['destination'] = f'/history/{target_season}'
        report['transaction_facts'] = facts['transactions']
        return page('Weekly League Report', render_report(report,
            data['league'].get('name', ''), target_season, target_week))
    return router
