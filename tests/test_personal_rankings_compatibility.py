"""Prepared snapshot → private HTTP → revisioned single-asset recovery controls."""
from __future__ import annotations

from contextlib import closing
import unittest
from unittest.mock import patch

from src.core.accounts.personal_store import load_personal
from tests import test_personal_rankings as fixtures


class PersonalCompatibilityRecoveryTests(unittest.TestCase):
    setUp = fixtures.PersonalRankingsHTTPTests.setUp
    state = fixtures.PersonalRankingsHTTPTests.state
    post = fixtures.PersonalRankingsHTTPTests.post
    initialize = fixtures.PersonalRankingsHTTPTests.initialize
    use_account = fixtures.PersonalRankingsHTTPTests.use_account

    def saved(self):
        return load_personal(self.store, 'account-a', 'league-1', 1)

    def test_inactive_priced_player_preserves_entire_saved_curve_without_repair(self):
        self.initialize()
        self.post('reorder', asset_id='player:3', to_position=1)
        self.post('tiers', asset_id='player:2', tier_start=True)
        self.post('preferences', asset_id='player:2', preferences={'target': True})
        before, saved = self.state(), self.saved()
        self.market.rows[1]['status'] = 'Inactive'
        self.market.generation = 'Market-B'
        after = self.state()
        self.assertTrue(after['personal_available'], after['limitations'])
        self.assertEqual(after['compatibility_issues'], [])
        self.assertEqual([(r['asset_id'], r['personal_value']) for r in after['rows']],
                         [(r['asset_id'], r['personal_value']) for r in before['rows']])
        inactive = next(r for r in after['rows'] if r['asset_id'] == 'player:2')
        self.assertIn('not confirmation', inactive['limitation'])
        self.assertEqual(self.saved(), saved)

    def test_inactivity_never_supplies_missing_price_or_overrides_identity(self):
        self.initialize()
        saved = self.saved()
        row = self.market.rows[1]
        row['status'] = 'Inactive'
        row['values']['market_value'] = None
        self.assertEqual(self.issue('player:2')['code'], 'market_price_missing')
        self.assertFalse(self.state()['personal_available'])
        row['values']['market_value'] = 0
        self.assertTrue(self.state()['personal_available'])
        self.assertEqual(next(r for r in self.state()['rows'] if r['asset_id'] == 'player:2')['market_value'], 0)
        row['asset_type'] = 'pick'
        self.assertEqual(self.issue('player:2')['code'], 'identity_conflict')
        self.assertEqual(self.saved(), saved)

    def test_missing_cohort_member_blocks_whole_curve_and_reappearance_restores_exactly(self):
        self.initialize()
        self.post('reorder', asset_id='player:3', to_position=1)
        saved, before = self.saved(), self.state()
        removed = self.market.rows.pop(1)
        self.market.generation = 'Market-B'
        blocked = self.state()
        self.assertFalse(blocked['personal_available'])
        self.assertTrue(all(r['personal_value'] is None for r in blocked['rows']))
        self.assertEqual(blocked['compatibility_issues'][0]['asset_id'], removed['asset_id'])
        self.market.rows.append(removed)
        self.market.generation = 'Market-C'
        restored = self.state()
        self.assertTrue(restored['personal_available'])
        self.assertEqual([(r['asset_id'], r['personal_value']) for r in restored['rows']],
                         [(r['asset_id'], r['personal_value']) for r in before['rows']])
        self.assertEqual(self.saved(), saved)

    def issue(self, key):
        return next(item for item in self.state()['compatibility_issues'] if item['asset_id'] == key)

    def remove(self, key, **kwargs):
        return self.post('remove_asset', asset_id=key, confirmation='REMOVE FROM CUSTOM ORDER', **kwargs)

    def test_market_update_and_new_assets_preserve_complete_saved_order_and_curve(self):
        self.initialize()
        self.post('reorder', asset_id='player:3', to_position=1)
        self.post('tiers', asset_id='player:3', tier_start=True)
        saved = self.saved()
        self.market.generation = 'Market-B'
        self.market.rows[0]['values']['market_value'] = 950
        before = self.state()
        self.assertTrue(before['personal_available'])
        self.market.rows.append(self.market.row('player:new', 999, 'QB', 'New ranked QB'))
        after = self.state()
        self.assertTrue(after['personal_available'])
        self.assertEqual(after['new_asset_ids'], ['player:new'])
        self.assertEqual({r['asset_id']: r['personal_value'] for r in before['rows']},
                         {r['asset_id']: r['personal_value'] for r in after['rows'] if r['custom_ranked']})
        self.assertEqual(self.saved(), saved)
        self.assertEqual(after['saved_asset_count'], 6)
        self.assertEqual(after['eligible_asset_count'], 7)

    def test_retired_asset_is_named_and_not_assumed_to_have_negative_value(self):
        self.initialize()
        saved = self.saved()
        self.market.rows[1]['status'] = 'Retired'
        issue = self.issue('player:2')
        self.assertEqual(issue['code'], 'asset_retired')
        self.assertEqual(issue['label'], 'Older producer')
        self.assertFalse(issue['retryable'])
        self.assertTrue(issue['can_remove'])
        state = self.state()
        self.assertFalse(state['personal_available'])
        self.assertIn('Older producer', state['limitations'][0])
        self.assertEqual(self.saved(), saved)
        self.assertTrue(all(row['personal_value'] is None for row in state['rows']))

    def test_missing_market_price_is_not_zero_and_retry_can_restore_without_write(self):
        self.initialize()
        saved = self.saved()
        self.market.rows[1]['values']['market_value'] = None
        issue = self.issue('player:2')
        self.assertEqual(issue['code'], 'market_price_missing')
        self.assertTrue(issue['retryable'])
        self.assertIn('not a zero', issue['reason'])
        self.market.rows[1]['values']['market_value'] = 0
        state = self.state()
        self.assertTrue(state['personal_available'])
        row = next(row for row in state['rows'] if row['asset_id'] == 'player:2')
        self.assertEqual(row['market_value'], 0)
        self.assertEqual(self.saved(), saved)

    def test_conflicting_identity_and_missing_identity_have_different_reasons(self):
        self.initialize()
        self.market.rows[1]['asset_type'] = 'pick'
        issue = self.issue('player:2')
        self.assertEqual(issue['code'], 'identity_conflict')
        self.market.rows = [row for row in self.market.rows if row['asset_id'] != 'player:2']
        issue = self.issue('player:2')
        self.assertEqual(issue['code'], 'asset_not_in_market')
        self.assertEqual(issue['label'], 'Player 2')
        self.assertIn('absent', issue['reason'])
        self.assertNotIn('retired', issue['reason'])

    def test_pick_owner_transition_preserves_identity_and_saved_protection(self):
        self.initialize()
        self.post('preferences', asset_id='pick:2028:1:4', preferences={'protect': True})
        saved = self.saved()
        pick = self.data['teams'][0]['picks_owned'].pop()
        pick['current_owner_id'] = 2
        self.data['teams'][1]['picks_owned'].append(pick)
        state = self.state()
        self.assertTrue(state['personal_available'])
        current = next(row for row in state['rows'] if row['asset_id'] == 'pick:2028:1:4')
        self.assertEqual(current['trade_asset_id'], '2028-R1-4')
        self.assertFalse(current['owned'])
        self.assertEqual(current['owner_roster_id'], 2)
        self.assertTrue(current['preferences']['protect'])
        self.data['teams'][1]['picks_owned'].remove(pick)
        issue = self.issue('pick:2028:1:4')
        self.assertEqual(issue['code'], 'pick_ownership_unavailable')
        self.assertIn('exact pick', issue['reason'])
        self.assertEqual(self.saved(), saved)

    def test_multiple_blockers_single_asset_recovery_preserves_intent_and_other_tiers(self):
        self.initialize()
        self.post('reorder', asset_id='player:3', to_position=1)
        self.post('tiers', asset_id='player:3', tier_start=True)
        self.post('tiers', asset_id='player:2', tier_start=True)
        self.post('preferences', asset_id='player:2', preferences={'avoid': True})
        self.post('preferences', asset_id='pick:2028:1:4', preferences={'protect': True})
        saved = self.saved()
        self.market.rows[1]['status'] = 'Retired'
        self.market.rows[3]['values']['market_value'] = None
        state = self.state()
        self.assertEqual(len(state['compatibility_issues']), 2)
        first = self.remove('player:2')
        self.assertEqual(first.status_code, 200, first.text)
        self.assertFalse(first.json()['personal_available'])
        self.assertEqual([issue['asset_id'] for issue in first.json()['compatibility_issues']], ['player:3'])
        saved_after = self.saved()
        self.assertEqual(saved_after['order'], [key for key in saved['order'] if key != 'player:2'])
        self.assertEqual(saved_after['baseline']['ids'], [key for key in saved['baseline']['ids'] if key != 'player:2'])
        self.assertEqual(saved_after['baseline']['generation'], saved['baseline']['generation'])
        self.assertEqual(saved_after['tiers'], ['player:3'])
        self.assertEqual(saved_after['preferences'], saved['preferences'])
        self.assertEqual(saved_after['revision'], saved['revision'] + 1)
        final = self.remove('player:3')
        self.assertEqual(final.status_code, 200, final.text)
        self.assertTrue(final.json()['personal_available'])
        self.assertEqual(self.saved()['preferences'], saved['preferences'])

    def test_recovery_requires_confirmation_exact_identity_and_latest_revision(self):
        self.initialize()
        state = self.state()
        saved = self.saved()
        denied = self.post('remove_asset', asset_id='player:2')
        self.assertEqual(denied.status_code, 422, denied.text)
        foreign = self.remove('player:not-in-saved-order')
        self.assertEqual(foreign.status_code, 409, foreign.text)
        self.assertEqual(self.saved(), saved)
        accepted = self.remove('player:2')
        self.assertEqual(accepted.status_code, 200, accepted.text)
        latest = self.saved()
        stale = self.remove('player:3', state=state)
        self.assertEqual(stale.status_code, 409, stale.text)
        self.assertEqual(self.saved(), latest)

    def test_last_ranked_asset_cannot_be_removed_or_silently_reset(self):
        self.initialize()
        for key in self.saved()['order'][:-1]:
            result = self.remove(key)
            self.assertEqual(result.status_code, 200, result.text)
        saved = self.saved()
        result = self.remove(saved['order'][0])
        self.assertEqual(result.status_code, 422, result.text)
        self.assertEqual(result.json()['status'], 'last_ranked_asset')
        self.assertEqual(self.saved(), saved)

    def test_recovery_and_edits_are_scoped_and_read_only_previews_do_not_write(self):
        self.initialize()
        self.market.rows[1]['values']['market_value'] = None
        saved = self.saved()
        with closing(self.store.connect()) as connection:
            before = '\n'.join(connection.iterdump())
        for _ in range(5):
            self.assertEqual(self.issue('player:2')['code'], 'market_price_missing')
        with closing(self.store.connect()) as connection:
            self.assertEqual('\n'.join(connection.iterdump()), before)
        self.use_account('account-b')
        response = self.remove('player:2')
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.saved(), saved)
        self.assertIsNone(load_personal(self.store, 'account-b', 'league-1', 1))

    def test_source_transition_during_recovery_rejects_without_edit(self):
        self.initialize()
        state = self.state()
        saved = self.saved()
        original = self.market.directory
        def change_source(**kwargs):
            result = original(**kwargs)
            self.market.generation = 'Market-B'
            return result
        with patch.object(self.market, 'directory', side_effect=change_source):
            response = self.remove('player:2', state=state)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.saved(), saved)

    def test_explicit_restart_reincludes_current_assets_and_preserves_sparse_intent(self):
        self.initialize()
        self.post('preferences', asset_id='player:2', preferences={'avoid': True})
        self.remove('player:2')
        saved = self.saved()
        self.market.rows.append(self.market.row('player:new', 999, 'QB', 'New ranked QB'))
        restarted = self.post('restart', confirmation='RESTART RANKINGS')
        self.assertEqual(restarted.status_code, 200, restarted.text)
        final = self.saved()
        self.assertIn('player:new', final['order'])
        self.assertIn('player:2', final['order'])
        self.assertEqual(final['preferences'], saved['preferences'])
        self.assertGreater(final['revision'], saved['revision'])
        self.assertTrue(restarted.json()['personal_available'])

    def test_missing_price_does_not_rewrite_supported_ownership_or_saved_protection(self):
        self.initialize()
        self.post('preferences', asset_id='player:3', preferences={'protect': True})
        saved = self.saved()
        self.market.rows[3]['values']['market_value'] = None
        state = self.state()
        row = next(row for row in state['rows'] if row['asset_id'] == 'player:3')
        self.assertTrue(row['owned'])
        self.assertEqual(row['owner_roster_id'], 1)
        self.assertTrue(row['preferences']['protect'])
        self.assertIsNone(row['market_value'])
        self.assertIsNone(row['personal_value'])
        self.assertEqual(self.saved(), saved)

    def test_preferences_use_supported_ownership_even_when_market_price_is_missing(self):
        self.initialize()
        self.post('preferences', asset_id='player:3', preferences={'protect': True})
        self.market.rows[3]['values']['market_value'] = None
        before = self.saved()
        state = self.state()
        row = next(row for row in state['rows'] if row['asset_id'] == 'player:3')
        self.assertTrue(row['owned'])
        response = self.post('preferences', asset_id='player:3', preferences={'protect': True, 'target': True})
        self.assertEqual(response.status_code, 200, response.json().get('status'))
        self.assertFalse(response.json()['personal_available'])
        after = self.saved()
        self.assertEqual(after['preferences']['player:3'], {'protect': True, 'target': True})
        self.assertEqual(after['order'], before['order'])
        self.assertEqual(after['tiers'], before['tiers'])
        self.assertEqual(after['revision'], before['revision'] + 1)
        self.assertTrue(next(row for row in response.json()['rows'] if row['asset_id'] == 'player:3')['owned'])

    def test_missing_price_does_not_allow_protection_with_foreign_conflicting_or_unknown_owner(self):
        self.initialize()
        self.market.rows[1]['values']['market_value'] = None
        saved = self.saved()
        foreign = self.post('preferences', asset_id='player:2', preferences={'protect': True})
        self.assertEqual(foreign.status_code, 422)
        self.assertEqual(foreign.json()['status'], 'not_owned')
        self.assertEqual(self.saved(), saved)
        self.market.rows[3]['values']['market_value'] = None
        self.data['teams'][1]['players'].append({'id': '3'})
        conflict = self.post('preferences', asset_id='player:3', preferences={'protect': True})
        self.assertEqual(conflict.status_code, 422)
        self.assertEqual(conflict.json()['status'], 'not_owned')
        self.assertEqual(self.saved(), saved)
        self.data['teams'][1]['players'].pop()
        self.data['teams'][0]['players'] = [row for row in self.data['teams'][0]['players'] if row['id'] != '3']
        unknown = self.post('preferences', asset_id='player:3', preferences={'protect': True})
        self.assertEqual(unknown.status_code, 422)
        self.assertEqual(unknown.json()['status'], 'not_owned')
        self.assertEqual(self.saved(), saved)

    def test_more_than_ten_thousand_unpriced_rows_do_not_expand_ranking_scan(self):
        self.initialize()
        self.market.rows[1]['values']['market_value'] = None
        self.market.rows.extend(self.market.row(f'player:unpriced-{index}', None, 'WR', f'Unpriced {index}')
                                for index in range(10_001))
        observed = []
        original = self.market.directory
        def record(**kwargs):
            result = original(**kwargs)
            observed.append((kwargs, result['total']))
            return result
        with patch.object(self.market, 'directory', side_effect=record):
            state = self.state()
        self.assertFalse(state['personal_available'])
        self.assertEqual(state['compatibility_issues'][0]['code'], 'market_price_missing')
        self.assertEqual(len(observed), 2)
        self.assertEqual(observed[0][0]['minimum'], 0)
        self.assertEqual(observed[0][1], 5)
        self.assertEqual(observed[1][0]['availability_asset_ids'], ('player:2',))
        self.assertEqual(observed[1][1], 1)

    def test_missing_saved_asset_queries_are_bounded_to_two_hundred_fifty_ids(self):
        self.market.rows.extend(self.market.row(f'player:extra-{index}', 100, 'WR', f'Ranked {index}')
                                for index in range(300))
        self.initialize()
        saved = self.saved()
        for row in self.market.rows:
            if row['asset_id'].startswith('player:extra-'):
                row['values']['market_value'] = None
        batches = []
        original = self.market.directory
        def record(**kwargs):
            if kwargs.get('availability_asset_ids'):
                batches.append(kwargs['availability_asset_ids'])
            return original(**kwargs)
        with patch.object(self.market, 'directory', side_effect=record):
            state = self.state()
        self.assertEqual(len(state['compatibility_issues']), 300)
        self.assertEqual([len(batch) for batch in batches], [250, 50])
        self.assertEqual(self.saved(), saved)

    def test_generation_transition_during_diagnostic_query_withholds_state(self):
        self.initialize()
        saved = self.saved()
        self.market.rows[1]['values']['market_value'] = None
        original = self.market.directory
        def transition(**kwargs):
            result = original(**kwargs)
            if kwargs.get('availability_asset_ids'):
                self.market.generation = 'Market-superseded'
            return result
        with patch.object(self.market, 'directory', side_effect=transition):
            response = self.client.get('/api/my-dtos')
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.saved(), saved)

    def test_removed_asset_sparse_flags_are_not_personal_market_prices(self):
        self.initialize()
        self.post('preferences', asset_id='player:2', preferences={'target': True})
        self.remove('player:2')
        state = self.state()
        row = next(row for row in state['rows'] if row['asset_id'] == 'player:2')
        self.assertFalse(row['custom_ranked'])
        self.assertIsNone(row['personal_value'])
        self.assertEqual(row['market_value'], 600)
        self.assertTrue(row['preferences']['target'])
        self.assertEqual(self.saved()['preferences'], {'player:2': {'target': True}})


if __name__ == '__main__':
    unittest.main()
