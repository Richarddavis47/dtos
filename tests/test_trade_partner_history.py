"""The link uses an exact, current workspace identity; it never authorizes History."""
import json
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium


class PartnerHistoryLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = launch_chromium(cls.playwright, headless=True)
        cls.page = cls.browser.new_page()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def run_link(self, *, workspace=None, package=None, context=None, modified=False, callback=False):
        source = Path('static/js/trade_workspace.js').read_text()
        function = source.split('  function appendPartnerHistory(', 1)[1].split("\n  el('trade-result').dataset.assessmentState", 1)[0]
        data = {
            'workspace': workspace if workspace is not None else {
                'workspace_context': {'binding': 'bound-A', 'league_id': 'league-1', 'roster_id': 1},
                'manager_context': {'league_id': 'league-1', 'roster_id': 1},
                'active_front_office': 1,
                'teams': [{'roster_id': 1, 'team_name': 'Mine'}, {'roster_id': 2, 'team_name': 'Their franchise'}],
            },
            'context': context if context is not None else {'identity': {'binding': 'bound-A', 'package': json.dumps(package if package is not None else [2, ['a'], ['2028-R1-4']])}},
            'modified': modified, 'callback': callback,
        }
        script = r"""
d=>{let saves=0,previews=0;
const node=(tag,text,cls)=>({tag,text,cls,attrs:{},setAttribute(k,v){this.attrs[k]=v},addEventListener(k,v){this[k]=v}});
const target={rows:[],append(x){this.rows.push(x)}};
const fn=new Function('workspace','active','node','persist','return (function appendPartnerHistory(' + %s + ')')(d.workspace,1,node,()=>saves++);
fn(target,d.context,d.callback?()=>previews++:null);
const before={saves,previews};
for(const link of target.rows) link.click({button:0,ctrlKey:d.modified,metaKey:false,shiftKey:false,altKey:false});
return JSON.parse(JSON.stringify({links:target.rows,before,saves,previews}));}
""" % json.dumps(function)
        return self.page.evaluate(script, data)

    def test_exact_link_does_not_save_until_followed(self):
        result = self.run_link()
        self.assertEqual(result['before'], {'saves': 0, 'previews': 0})
        self.assertEqual(result['saves'], 1)
        self.assertEqual(result['links'][0]['href'], '/history/team/league-1%3Afranchise%3A2')
        self.assertEqual(result['links'][0]['text'], 'See franchise trade history')
        self.assertIn('Their franchise', result['links'][0]['attrs']['aria-label'])

    def test_recommendation_retains_preview_only_on_normal_click(self):
        self.assertEqual(self.run_link(callback=True)['previews'], 1)
        self.assertEqual(self.run_link(callback=True)['saves'], 0)
        self.assertEqual(self.run_link(callback=True, modified=True)['previews'], 0)
        self.assertEqual(self.run_link(modified=True)['saves'], 0)

    def test_missing_self_unknown_and_malformed_partner_are_omitted(self):
        for package in ([0, [], []], [1, [], []], [3, [], []], ['2', [], []], [2, [], None], [2, []]):
            with self.subTest(package=package):
                self.assertEqual(self.run_link(package=package)['links'], [])

    def test_saved_context_cannot_cross_binding_or_declared_league(self):
        for context in (
            {'identity': {'binding': 'other', 'package': '[2,[],[]]'}},
            {'identity': {'binding': 'bound-A', 'package': 'truncated'}},
            {'identity': {'binding': 'bound-A', 'package': '[2,[],[]]'}, 'evaluation': {'provenance': {'inputs': {'league_id': 'other'}}}},
        ):
            with self.subTest(context=context):
                self.assertEqual(self.run_link(context=context)['links'], [])

    def test_ambiguous_or_changed_workspace_is_omitted(self):
        baseline = self.run_link()['links']
        self.assertEqual(len(baseline), 1)
        workspace = {'workspace_context': {'binding': 'bound-A', 'league_id': 'league-1', 'roster_id': 1},
                     'manager_context': {'league_id': 'league-1', 'roster_id': 1}, 'active_front_office': 1,
                     'teams': [{'roster_id': 1}, {'roster_id': 2}, {'roster_id': 2}]}
        self.assertEqual(self.run_link(workspace=workspace)['links'], [])
        workspace['teams'].pop()
        for field in ('active_front_office',):
            workspace[field] = 3
            self.assertEqual(self.run_link(workspace=workspace)['links'], [])
        workspace['active_front_office'] = 1
        workspace['workspace_context']['league_id'] = 'other'
        self.assertEqual(self.run_link(workspace=workspace)['links'], [])


if __name__ == '__main__':
    unittest.main()
