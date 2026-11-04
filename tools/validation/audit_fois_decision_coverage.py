"""Bounded local retained-evidence audit; prints aggregates, writes no history."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from src.core.fois.assessment_export import assessment_record

from src.core.fois.history import load_results_history
from src.core.history_context.store import canonical_history_store
from src.core.intelligence_memory import intelligence_checkpoint_store
from src.core.intelligence_memory.checkpoint_flight import checkpoint_read_flight


def manager_panel(histories, *, league_id=None):
    """Summarize actual evaluator output, without synthesizing quality grades."""
    panel = {}
    for roster, history in sorted(histories.items()):
        categories = {}
        for category, key in (('trading', 'trades'), ('drafting', 'drafts'), ('waivers', 'waivers')):
            rows = history.get(key) or ()
            categories[category] = dict(history['decision_coverage'][category])
            categories[category]['derived_assessments'] = [
                assessment_record(row, category, league_id=league_id, franchise_id=roster)
                for row in rows]
            categories[category]['decisions_with_market_references'] = sum(
                bool(row.get('decision_time_market_references')) for row in rows)
            if category == 'drafting':
                categories[category]['alternative_assessments'] = sum(
                    any(d.get('dimension') == 'market_relative_selection' for d in
                        (row.get('decision_evaluation') or {}).get('process', {}).get('assessment', ()))
                    for row in rows)
            if category == 'waivers':
                categories[category]['faab'] = {
                    'known': sum(row.get('faab_bid') is not None for row in rows),
                    'explicit_zero': sum(row.get('faab_bid') == 0 for row in rows),
                    'unavailable': sum(row.get('faab_bid') is None for row in rows)}
        contexts = [row['decision_evaluation']['historical_roster_context']
                    for key in ('drafts', 'waivers') for row in history.get(key, ())
                    if (row.get('decision_evaluation') or {}).get('historical_roster_context')]
        panel[roster] = {
            'owner_by_season': history.get('owner_by_season', {}),
            'results_by_season': history.get('seasons', []),
            'categories': categories,
            'historical_roster_context': {
                'decision_references': len(contexts),
                'unique_states': len({row['reference'] for row in contexts}),
                'precision': dict(Counter(row['precision'] for row in contexts)),
                'ownership_availability': dict(Counter(row['ownership_availability'] for row in contexts)),
                'scope': 'draft_and_waiver_context_references_not_roster_quality_grade'},
            'overall_quality': None,
            'overall_quality_reason': 'coverage_panel_not_quality_calibration'}
    return panel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--league', required=True)
    args = parser.parse_args()
    with checkpoint_read_flight(intelligence_checkpoint_store) as reader:
        histories = load_results_history(canonical_history_store, args.league, checkpoint_reader=reader)
        output = {'league': args.league, 'checkpoint_generation': reader.generation,
                  'scope': 'local_retained_evidence_not_production_parity', 'managers': {}}
        output['managers'] = manager_panel(histories, league_id=args.league)
    print(json.dumps(output, sort_keys=True))


if __name__ == '__main__':
    main()
