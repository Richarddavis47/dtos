"""Pure comparison admission; source numbers remain unchanged, including zero."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
import playwright


class OfferComparisonTests(unittest.TestCase):
    def fixture(self):
        baseline = dict(league='league-a', roster=1, ownership='owned-a', lineup='lineup-a',
                        season=2026, week=8, scoring='scoring-a', projection='projection-a', provider='Sleeper')
        scope = dict(binding='account/session/league/franchise', league='league-a', roster=1)
        context = dict(identity=dict(market='market-a'), evaluation=dict(provenance=dict(inputs={})))
        entry = dict(schema=1, scope=scope, baseline=baseline, context=context,
                     summary=dict(mode='neutral', lineup=dict(state='supported', pre_total=100,
                                                             post_total=104, delta=4, weeks=[8])))
        current = dict(baseline, scope=scope, market='market-a', observed={}, personalStale=False)
        return [entry, deepcopy(entry)], current

    def compare(self, entries, current):
        bundled = Path(playwright.__file__).parent / 'driver' / ('node.exe' if os.name == 'nt' else 'node')
        node = shutil.which('node') or (str(bundled) if bundled.is_file() else None)
        self.assertIsNotNone(node, 'The required browser runtime must include Node')
        module = Path(__file__).resolve().parents[1] / 'static/js/trade_comparison.js'
        source = "const api=require(process.argv[1]);let d=JSON.parse(process.argv[2]);const before=JSON.stringify(d);let r=api.compatibility(d.entries,d.current);if(JSON.stringify(d)!==before)throw Error('mutated evidence');console.log(JSON.stringify(r));"
        result = subprocess.check_output([node, '-e', source, str(module),
                                          json.dumps(dict(entries=entries, current=current))], text=True)
        return json.loads(result)

    def test_complete_and_explicit_zero_use_the_same_recorded_roster(self):
        entries, current = self.fixture()
        entries[1]['summary']['lineup'].update(post_total=100, delta=0)
        result = self.compare(entries, current)
        self.assertTrue(result['supported'])
        self.assertEqual(result['baseline'], 100)
        self.assertTrue(self.compare(entries[:1], current)['supported'])
        self.assertFalse(self.compare(entries * 2, current)['supported'])

    def test_each_required_identity_and_current_baseline_is_checked(self):
        entries, current = self.fixture()
        for key in entries[0]['baseline']:
            with self.subTest(key=key):
                altered = deepcopy(entries)
                altered[1]['baseline'][key] = 'different'
                self.assertFalse(self.compare(altered, current)['supported'])
                altered[1]['baseline'][key] = None
                self.assertFalse(self.compare(altered, current)['supported'])
        for key in ['projection', 'scoring', 'season', 'week', 'lineup', 'provider', 'ownership', 'market']:
            with self.subTest(current=key):
                altered = dict(current, **{key: None})
                self.assertFalse(self.compare(entries, altered)['supported'])
        entries[1]['summary']['lineup'].update(pre_total=101, post_total=105)
        self.assertIn('before-trade', self.compare(entries, current)['reason'])

    def test_stale_provisional_missing_and_conflicting_numbers_are_withheld(self):
        entries, current = self.fixture()
        for change in [dict(delta=None), dict(post_total=None), dict(delta=0), dict(state='provisional'), dict(weeks=[9])]:
            with self.subTest(change=change):
                altered = deepcopy(entries)
                altered[1]['summary']['lineup'].update(change)
                self.assertFalse(self.compare(altered, current)['supported'])
        entries[1]['context']['stale_reason'] = 'Failed source refresh; retained context'
        result = self.compare(entries, current)
        self.assertEqual(result['state'], 'stale')
        self.assertIn('Failed source refresh', result['reason'])
        entries[1]['context'].pop('stale_reason')
        entries[1]['summary']['lineup']['post_total'] = None
        self.assertTrue(self.compare(entries, current)['shared_identity'])
        self.assertTrue(self.compare(entries[:1], current)['supported'])

    def test_valuation_modes_do_not_blend_and_retention_does_not_claim_currentness(self):
        entries, current = self.fixture()
        entries[1]['summary']['mode'] = 'custom'
        entries[1]['summary']['method'] = 'relative-priced-order-v1'
        current['personalContext'] = dict(revision=1, market='personal-market-a', baseline='personal-baseline-a',
                                          method='relative-priced-order-v1')
        entries[1]['summary']['personalContext'] = dict(current['personalContext'])
        entries[1]['retained'] = True
        result = self.compare(entries, current)
        self.assertTrue(result['supported'])
        self.assertEqual(result['state'], 'retained')
        self.assertIn('NOT REVALIDATED', result['reason'])
        current['personalStale'] = True
        self.assertFalse(self.compare(entries, current)['supported'])
        current['personalStale'] = False
        current['personalContext']['revision'] = 2
        self.assertFalse(self.compare(entries, current)['supported'])
        current['personalContext']['revision'] = 1
        entries[1]['scope']['binding'] = 'another-account'
        self.assertFalse(self.compare(entries, current)['supported'])

    def test_untrusted_stored_entries_are_bounded_before_rendering(self):
        module = Path(__file__).resolve().parents[1] / 'static/js/trade_comparison.js'
        bundled = Path(playwright.__file__).parent / 'driver' / ('node.exe' if os.name == 'nt' else 'node')
        node = shutil.which('node') or str(bundled)
        code = """const assert=require('assert'),api=require(process.argv[1]);
const entry={id:'evaluated-id',summary:{verdict:'Limited',mode:'neutral'},assets:{sent:[{id:'pick:2028:1:4',label:'Exact pick'}],received:[]}};
assert(api.wellFormed(entry));for(const value of [null,{}, {...entry,summary:[]},{...entry,assets:{sent:[null],received:[]}}, {...entry,assets:{sent:new Array(33).fill({id:'a',label:'a'}),received:[]}}])assert(!api.wellFormed(value));
assert.equal(entry.assets.sent[0].id,'pick:2028:1:4');console.log('bounded stored state verified');"""
        self.assertIn('verified', subprocess.check_output([node, '-e', code, str(module)], text=True))
