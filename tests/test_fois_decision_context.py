import unittest
from types import SimpleNamespace
from src.core.fois.decision_context import draft_alternatives, roster_context


class DecisionContextTests(unittest.TestCase):
    def test_alternatives_need_contemporaneous_pool_not_later_success(self):
        decision = dict(draft_id='d', player_id='selected', pick_number=2,
                        occurred_at='2024-08-01T00:00:00Z')
        rows=[{'payload':dict(draft_id='d',player_id='taken',pick_no=1)},
              {'payload':dict(draft_id='d',player_id='later-star',pick_no=3)}]
        self.assertEqual(draft_alternatives(decision,rows),())
        decision['eligible_pool']=dict(reference='historical-pool',as_of='2024-07-01T00:00:00Z',
                                       player_ids=['taken','selected','available'])
        self.assertEqual([r['asset_id'] for r in draft_alternatives(decision,rows)],['available'])
        decision['eligible_pool']['as_of']='2025-01-01T00:00:00Z'
        self.assertEqual(draft_alternatives(decision,rows),())

    def test_anchor_is_not_exact_selection_and_is_strictly_before(self):
        class States:
            def reconstruct(self,league,franchise,boundary):
                self.boundary=boundary
                return SimpleNamespace(state_id='state',availability=SimpleNamespace(value='partial'),
                    coverage={'ownership':SimpleNamespace(availability=SimpleNamespace(value='partial'),reason_codes=('uncertain',))},
                    players=(),draft_picks=(),history_generation='g')
        states=States()
        result=roster_context(states,'L','1',dict(season=2024,owner_id='gm',draft_start_at='2024-08-01T00:00:00Z'))
        self.assertEqual(result['precision'],'pre_draft_anchor_not_exact_selection')
        self.assertEqual(states.boundary.mode.value,'before')
        self.assertEqual(result['ownership_availability'],'partial')
