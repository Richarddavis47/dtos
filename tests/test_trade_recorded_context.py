"""Exercise actual client serializer/decoder without copying its implementation."""
from pathlib import Path
import unittest


class RecordedContextTests(unittest.TestCase):
    def test_large_comparison_survives_original_limits(self):
        source = Path('static/js/trade_workspace.js').read_text()
        def function(name, following):
            return source[source.index('  function ' + name):source.index(following, source.index('  function ' + name))]
        script = '\n'.join([
            function('boundedEvidence', '  const packageIdentity'),
            function('compactRetainedEvaluation', '  function retainedReserveRow'),
            function('decisionPresentation', '  function catalystDelta'),
            function('valuationSummary', '  function appendCurrentLineupSummary'),
            r"""
const assert = {equal(a,b){if(a !== b) throw Error('Values differ');}, deepEqual(a,b){if(JSON.stringify(a)!==JSON.stringify(b)) throw Error('Recorded comparison differs');}};
const displayMarket = String;
for (const value of [null,42,'invalid',[]]) assert.deepEqual(recordedEvaluation(value),{});
for (const [method, label] of [['personal-current-market-slot-curve-v1','Absolute slot'],['personal-relative-priced-order-v1','Relative priced order'],[undefined,'method not recorded'],['foreign-relative-method','method not recorded']]) {
 const e={personalization:{mode:'custom',method},personal_value_evidence:{sent:{total:10},received:{total:20}}};
 assert.equal(valuationSummary(e),'Your Custom values · '+label+': 10 sent / 20 received');
}
const period = {delta:-2.68, weeks:[10], pre_total:120, post_total:117.32, qualification:'provisional', notes:'availability uncertain '.repeat(80)};
const original = {personalization:{mode:'custom',method:'personal-current-market-slot-curve-v1'},decision_context:{summary:'retained '.repeat(200),lineup_comparisons:{current_week:{delta:0.17,weeks:[10]}},partner_lineup_comparisons:{current_week:period}}};
original.reserve_evidence = {active:{limitations:'reserve evidence '.repeat(1400)}};
const saved = recordedEvaluation(original);
const restored = recordedEvaluation(JSON.parse(JSON.stringify(saved)));
assert.deepEqual(decisionPresentation(restored).partner_lineup_comparisons.current_week, period);
assert.equal(restored.personalization.method, original.personalization.method);
assert.equal(typeof restored.reserve_evidence.active.limitations, 'string');
assert.equal(restored.reserve_evidence.active.limitations.length,1600);
assert.equal(decisionPresentation(restored).lineup_comparisons.current_week.delta,0.17);
assert.equal(original.decision_context.partner_lineup_comparisons.current_week,period);
const broken = structuredClone(restored); broken.decision_context.partner_lineup_comparisons.current_week.chunks.pop();
assert.equal(decisionPresentation(broken).partner_lineup_comparisons.current_week,null);
""",
        ])
        from playwright.sync_api import sync_playwright
        from tools.validation.browser_runtime import launch_chromium
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page = browser.new_page()
                page.evaluate('() => {' + script + '}')
            finally:
                browser.close()
