"""Roster assessment from explicit generation-bound evidence dimensions."""
from dataclasses import replace
from typing import Any
from src.core.roster_intelligence.models import GradeDimension, PlayerCard, PositionRoomReport, RosterReport
from src.core.team_intelligence import build_team_intelligence
from src.core.intelligence.team_assessment import build_team_assessment
from src.core.intelligence.roster_evidence import build_roster_evidence
from src.core.intelligence.roster_grading import PlayerGradingEvidence, grade_roster_evidence
from src.core.valuation.player_methodology import assess_prepared_intrinsic
from src.core.trade_intelligence.lineup import optimal_legal_lineup
from src.core.valuation import cached_market_consensus

POSITIONS = ("QB", "RB", "WR", "TE")

def evaluate_roster(intelligence: Any) -> RosterReport:
    context = intelligence.context
    ids = {str(p.get('id') or p.get('player_id')) for d in intelligence.decisions.values() for p in d.profile.players}
    league_market_values = cached_market_consensus(context.cached_data.get('market_data') or {}, ids)
    grading, league_players = {}, {}
    for roster_id, other in intelligence.decisions.items():
        roster = next(team for team in context.teams if int(team.get('roster_id') or 0) == roster_id)
        scoped = replace(context, active_roster_id=roster_id, roster=roster)
        lineup = build_roster_evidence(scoped)
        projection_rows = (context.projection_snapshot or {}).get('players') or {}
        prepared = context.cached_data.get('canonical_player_production')
        evidence_players = []
        for player in other.profile.players:
            player_id = str(player.get('id') or player.get('player_id'))
            quality = assess_prepared_intrinsic(prepared=prepared, league_id=context.league_id,
                player_id=player_id, position=str(player.get('position') or ''), age=player.get('age')) if prepared else None
            components = {item.name: item.score for item in quality.components} if quality else {}
            projected = projection_rows.get(player_id) or {}
            points = projected.get('weekly_projected_points') if lineup.projection_week is not None and projected.get('week') == lineup.projection_week else None
            price, price_confidence, _ = league_market_values.get(player_id, (None, 0, None))
            evidence_players.append(PlayerGradingEvidence(player_id, price,
                components.get('reference_production'), points, components.get('position_lifecycle'),
                quality.confidence if quality else 0, price_confidence,
                int(projected.get('projection_confidence') or 0)))
        backup = None
        if lineup.optimal_lineup_projection is not None:
            reserves = [{'id': item.player_id, 'position': player.get('position'), 'projected_points': item.projected_points}
                for item, player in zip(evidence_players, other.profile.players)
                if item.player_id not in lineup.optimal_starter_ids
                and str(player.get('roster_slot') or '').upper() not in {'IR', 'TAXI', 'RESERVE'}]
            backup_result = optimal_legal_lineup(reserves, context.settings.get('roster_positions') or ())
            backup = backup_result.projected_points if backup_result.available else 0
        grading[roster_id] = grade_roster_evidence(league_id=context.league_id, roster_id=roster_id,
            generation=context.evidence_generation, players=tuple(evidence_players),
            actual_starter_ids=lineup.actual_starter_ids, optimal_starter_ids=lineup.optimal_starter_ids,
            actual_points=lineup.actual_lineup_projection, optimal_points=lineup.optimal_lineup_projection,
            legal_backup_points=backup)
        league_players[roster_id] = {}
        for item, player in zip(evidence_players, other.profile.players):
            row = projection_rows.get(item.player_id) or {}
            same_week = lineup.projection_week is not None and row.get('week') == lineup.projection_week
            league_players[roster_id][item.player_id] = PlayerCard(
                item.player_id, 'Intrinsic tier unavailable', 'Unavailable', None,
                'Unavailable' if player.get('age') is None else f"Age {player['age']}",
                'Unavailable', item.market_price, None, None, None, None, None, 'Unavailable',
                row.get('weekly_ceiling') if same_week else None,
                row.get('weekly_floor') if same_week else None,
                'Production quality unavailable' if item.production_quality is None else f'Demonstrated quality {item.production_quality}/100',
                'Longevity context is not a dynasty price.', 'Review evidence')
    league_rooms = {key: dict.fromkeys(POSITIONS) for key in grading}
    league_metrics = {key: {name: item.value for name, item in row.dimensions.items()} for key, row in grading.items()}
    teams, summary = build_team_intelligence(intelligence.decisions, league_rooms, league_players, league_metrics, grading=grading)
    assessment = build_team_assessment(context, teams[context.active_roster_id])
    window = assessment.team.competitive_window
    rooms = {p: PositionRoomReport(p, GradeDimension('Position evidence', None, 'Unavailable',
        'No generic player-score aggregate.'), (), None, len(context.teams), None,
        ('See distinct lineup and Market dimensions.',)) for p in POSITIONS}
    metrics = dict.fromkeys(('Roster Health', 'Elite Assets', 'Cornerstones', 'Trade Chips',
        'Roster Flexibility', 'Elite Concentration', 'Positional Balance', 'Average Starter Age'))
    metrics.update({'Championship Window': None, 'Future Window': None,
        'Weekly Ceiling': assessment.weekly_ceiling, 'Weekly Floor': assessment.weekly_floor,
        'Weekly Projection Units': 'fantasy_points',
        'Actual Lineup Projection': assessment.roster_evidence.actual_lineup_projection,
        'Optimal Projected Lineup': assessment.roster_evidence.optimal_lineup_projection,
        'Evidence Dimensions': grading[context.active_roster_id].dimensions, 'League Rankings': {}})
    return RosterReport(window.classification.value, ' '.join(window.reasons), rooms,
        league_players[context.active_roster_id], metrics, 'Unavailable', 'Unavailable', (),
        assessment.limitations, league_rooms, league_players, league_metrics, teams, summary, assessment)
