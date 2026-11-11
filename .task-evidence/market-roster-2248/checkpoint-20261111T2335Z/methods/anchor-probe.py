"""Additional exact-app-code 320px anchor round trip; no source edits or production calls."""
from pathlib import Path
import json,os,sys,unittest,subprocess
sys.path.insert(0,'/app');base=Path('/tmp/anchor-fixture');base.mkdir()
for key,name in {'CACHE':'cache.json','PROJECTION_DB':'projections.sqlite3','METADATA_DB':'metadata.sqlite3','INTELLIGENCE_CHECKPOINT':'intelligence.sqlite3','FOIS_DB':'fois.sqlite3','HISTORY_DB':'history.sqlite3','ACCOUNT_DB':'accounts.sqlite3'}.items():os.environ['DTOS_'+key+'_FILE']=str(base/name)
os.environ.update(DTOS_DURABLE_HISTORY_REQUIRED='0',SLEEPER_BASE_URL='http://127.0.0.1:9/v1',SLEEPER_LEAGUE_ID='1804000000000000000',DTOS_FIXTURE_ROOT=str(base),DTOS_SLEEPER_SEASON_CACHE_ROOT=str(base/'seasons'),DTOS_HISTORY_STORAGE_ROOT=str(base),DTOS_MARKET_NEED_EVIDENCE='/output/browser')
cg=Path('/sys/fs/cgroup');assert int((cg/'memory.max').read_text())==2147483648
source=Path('/app/tests/test_market_roster_relevance_browser.py').read_text();source=source.replace('for sf in (False, True):','for sf in (False,):',1);start=source.index('                    for width, height in [');end=source.index('                        touch = ',start);source=source[:start]+'                    for width, height in [(320, 432)]:\n'+source[end:]
needle='''                                panel = page.locator("#market-roster-movement")''';assert needle in source;source=source.replace(needle,'''                                page.get_by_role("link", name="Movement and roster relevance ↓", exact=True).tap()
                                page.wait_for_url("**#market-roster-movement")
'''+needle,1)
namespace={'__name__':'additional_market_anchor_probe'};exec(compile(source,'additional_market_anchor_probe.py','exec'),namespace);result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([namespace['MarketRosterBrowserTests']('test_prepared_market_to_trade_and_back_preserves_existing_work')]))
root=Path('/output');row=dict(passed=result.wasSuccessful(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),limit=int((cg/'memory.max').read_text()),peak=int((cg/'memory.peak').read_text()),events=dict(line.split() for line in (cg/'memory.events').read_text().splitlines()),scope='Supplemental unchanged-source 1QB/KDEF320px native section-anchor -> TradeFor -> contextualBack across filter/hash steps -> original Evaluate. Existing assertions retained; not owner live or physicalSafari.')
(root/'result.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row));raise SystemExit(not row['passed'])
