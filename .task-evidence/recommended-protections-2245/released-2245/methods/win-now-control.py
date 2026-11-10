"""Additional exact-source Win Now / Neutral acceptance, outside application code."""
from copy import deepcopy
import sys,unittest
sys.path.insert(0,'/app')
from tests import test_recommended_protections_browser as protection

class WinNowControl(unittest.TestCase):
    def test_explicit_neutral_search(self):
        case=protection.RecommendedProtectionBrowserTests('test_exact_pick_player_and_phone_search_preserve_other_same_round_pick')
        self.addCleanup(case.doCleanups)
        helper,f,page,requests=case.fixture()
        saved=deepcopy(f.editor.state())
        helper.ready(page,'/trades/recommended')
        case.protect(page,'2029-R1-1')
        case.protect(page,'a')
        page.select_option('#trade-valuation-mode','neutral')
        page.select_option('#trade-strategy','WIN NOW')
        before=len([r for r in requests if r[0]=='POST'])
        self.assertEqual(before,0)
        payload,body=case.generate(page)
        self.assertEqual(payload['valuation_mode'],'neutral')
        self.assertEqual(payload['strategy'],'WIN NOW')
        self.assertEqual(set(body['constraints']['protected_assets']),{'2029-R1-1','a'})
        rows=body.get('results',[])+body.get('exploratory_results',[])
        for row in rows:
            self.assertTrue({'2029-R1-1','a'}.isdisjoint(row['proposal']['assets_sent']))
        self.assertEqual(f.editor.state(),saved)
        case.record('win-now-neutral',dict(payload=payload,body=body,normal_admission=True,completed=True,
                    saved_preferences_unchanged=True,qualified_count=sum(r.get('evaluation',{}).get('generated_trade_eligible') is True for r in rows)),page)

if __name__=='__main__':unittest.main(verbosity=2)
