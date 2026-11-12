"""Completion claims require actual mandatory validation and publication receipts."""
from pathlib import Path
import json
B=Path(__file__).resolve().parent
def load(name): return json.loads((B/name).read_text())
s=load('source.json'); local=load('local-verified.json'); host=load('host-canonical-verified.json'); native=load('hosted-artifacts-verified.json'); product=load('product-test-counts.json'); release=load('release-verified.json'); production=load('production-verified.json'); merge=load('merge-verified.json'); controller=load('publisher-controller.json')
assert local['all_local_gates_passed'] and host['all_gates_passed'] and native['passed'] and len(native['originals'])==15
assert local['tests']==host['tests']==4419 and product['total']==916
assert release['published'] and release['immutable'] and production['passed'] and release['commit']==production['commit']==merge['merge_commit'] and release['tree']==production['tree']==s['tree']
(B/'APPLICATION_VALIDATION.md').write_text(f'''# Exact-source validation — build 2249

Candidate `{s['candidate']}`, tree `{s['tree']}`. All results here require completed original records.

| Scope | Completed result | Original evidence |
|---|---|---|
| Frozen-source focused controls | 123 passed; zero failures/errors/skips | focused/ and focused-console/ |
| Local Python 3.14.3 canonical | 4,419 passed; all ten gates | local-canonical/ and local-canonical-unittest-console-log/ |
| Hosted Python 3.14.3 canonical | 4,419 passed; all ten gates | hosted-canonical/ and hosted-canonical-unittest-console-log/ |
| Required hosted jobs | 13 successful across four workflows | hosted-final-records.json and job-consoles/ |
| Product executions | 916 = 742 + 35 + 139 | product-test-counts.json |
| Original native archives | 15 API sizes/SHA256/ZIP CRCs and specialized guards verified | hosted-artifacts-verified.json |
| Fresh native resource protocols | Three passed under an actual 2 GiB limit | resource-originals/ |
| New source-scope tests | 18 unit/lifecycle methods plus two browser methods; included in full suite | source patch, canonical test events |
| Browser journeys | Eight supported roundtrips: 1-QB/K/DEF and Superflex at four viewports; five withholding controls | roster-browser/ |
| Supplemental local capital captures | Two unchanged browser methods passed, actual 2 GiB, eight league/viewport captures | local-capital-capture/ |
| Scoped Actions publisher | 138 passed separately from app suite | publisher-final-exact-controls.log |

Official full command: `python -m tools.validation.validate_release`. Exact runner, command arguments, source identity, image and mounts are in canonical-invocation.json and methods/. Focused invocation is in focused-final-invocation.json. Full runs enforce 2,147,483,648 bytes, no extra swap, two CPUs, network disabled and nonroot 1000. No resource, browser, security or responsiveness assertion was relaxed.

Local elapsed {local['elapsed_seconds']:.3f}s; kernel peak {local['kernel_peak']:,} bytes. Hosted elapsed {host['elapsed_seconds']:.3f}s; kernel peak {host['kernel_peak']:,} bytes. These suites include deliberate pressure fixtures and are not a production memory forecast. Final original result, memory, events, manifest and process-cleanup files distinguish actual completion from deferral. Public HTTP timings include network and do not establish isolated server latency.

Counts overlap: focused, Product and canonical controls must not be added as unique tests. Keyboard/touch Chromium emulation is not physical iPhone/Safari acceptance. Exact console/event/memory bytes are split only at UTF-8 boundaries, with whole-file and part SHA256; original line endings are preserved.

## Earlier attempts remain separate

The first candidate c821a0bcd8349ae774cd8cd1834fb6e37ad4d18e narrowed the separate full-publication source-clock disclosure as well as freshness. Existing My Team (255 executions) and Welcome (412 executions) controls each correctly failed one assertion: six clocks instead of 238. Final source restores all clocks and labels roster-comparison freshness independently. Those original test files are byte-identical to production.

The superseded c821 local canonical run was cancelled at approximately 275 seconds after that known defect, not passed. Its six preliminary gates completed; the unittest gate and final three did not complete. Superseded hosted canonical/Product cancellations and completed failed jobs remain original historical evidence. Earlier two browser-construction attempts failed navigation/return-context assumptions; the tests now exercise the normal navigation and contextual Back flow without dropping draft assertions. Development passes are not relabeled frozen-source acceptance.

The unpublished prior-evidence container initially used a descriptive scope label where the existing publisher required `prior-attempts-only`. That schema mismatch was corrected without changing the guard or any of its 156 raw evidence members. The original packaging container remains retained locally; its original manifest/hash and before/after guard outcome are published in prior-package-scope-correction.json. No test was rerun or relabeled by this correction.

The first complete handoff archive also failed its publication precheck because the successful official canonical harness had not set DTOS_COMPARE_EVIDENCE. Original canonical tests and all 746 manifest entries stayed unchanged. Two unchanged capital browser methods then passed in a fresh enforced 2 GiB container, peak 704,552,960 bytes, producing eight separate source-bound captures. The tooling collector routes the unchanged guard to local-capital-capture/ and labels that origin explicitly. All other validation guard function bodies are identical. No hosted capture was relabeled local and no full suite was repeated. See recovery-packaging-failure.json, original packaging log and publisher-local-capital-prefix-correction.json.

See PRIOR_ATTEMPTS.md, prior-attempts/ and immutable Prior-attempts.zip. The separately retained cancelled Trade artifact is inside the release handoff ZIP under prior-originals/source-c821/. A never-started local container failed its unchanged 8 GiB scratch guard and executed no tests. No incomplete, cancelled or deferred operation counts as completion.
''')
(B/'REPORT.md').write_text(f'''# Supported roster evidence without unrelated catalog dependencies

Released **v{s['version']} / build {s['build']}**, [PR #338](https://github.com/Richarddavis47/dtos/pull/338). [Immutable release]({release['url']}). Deployed commit `{production['commit']}`; validated tree `{s['tree']}`. Candidate `{s['candidate']}`; baseline `{s['baseline']}`. The shared correction is verified; owner-authenticated Granite recovery remains unverified.

## Confirmed cause and correction

The baseline freshness calculation examined every canonical catalog projection leaf. In a matched native Sleeper fixture, adding one unrostered missing-projection leaf left all 46 rostered players, 174.0 owner optimal points, the same ten legal starters and a +10.0 existing RB addition scenario unchanged. Nevertheless, the roster changed from current to provisional and the existing personalized Market action disappeared. The missing projection was genuine; making it a dependency of an unrelated roster comparison was the defect. The RB addition scenario is not proof that a particular Market player improves the lineup.

Freshness now depends on league roster references, excluding only explicit IR/taxi/reserve storage and explicit lineup ineligibility, consistently with existing legal assignments. Eligible reserves, peer teams, K/DEF and FLEX dependencies remain conservative. Atomic league/season/scoring/generation compatibility still examines every canonical leaf. The complete source-clock disclosure remains intact; its full-publication scope is distinguished from roster-comparison freshness. Source rows and all numerical values are unchanged. A post-trade roster independently rechecks freshness, including an incoming formerly stored asset.

## What became usable

Matched current, compatible 1-QB/K/DEF and Superflex fixtures preserve existing supported starter/depth findings despite an unrelated missing/stale catalog leaf or explicitly stored asset. My Team retains the existing need action; Market can expose its prepared positional relevance and exact-player Trade For handoff. Editable controls wait for explicit Generate. Contextual Back preserves the draft, exact protections, valuation and existing work. No new opportunity score, projection, availability provider, search, optimizer, source request, permanent data store or runtime owner was added.

This is independently supported positional relevance, not exact-player lineup improvement, replacement-depth certainty, affordability, counterparty intent or a qualified bilateral recommendation.

## What remains unknown

Unknown eligible K/DEF or FLEX availability, missing eligible reserves, stale source evidence, failed refreshes and incompatible publications remain qualified. Positive projections, Active roster labels, absent injury designations, byes and DNPs do not establish participation. Missing remains missing; explicit zero and negative precision remain intact. Full source provenance includes unsupported catalog clocks without falsely making them freshness dependencies.

The supplied owner observation established Granite's provisional Week 10, 10/10 slots and 9/12 comparison state, not its particular cause. Codex could not reproduce the owner's authenticated session or inspect current player-week reasons. This session exposes neither the supported browser-control interface nor Render Shell. The unchanged external inspection 401 was not retried, and no configured token left Render. Main Chat's earlier Render-local identity 200 remains supplied evidence, not a check reproduced here.

## Validation and preservation

Final-source focused 123 passed; local and hosted canonical each passed 4,419 tests and all ten gates; all 13 required hosted jobs passed, including 916 Product executions. All 15 original native archives passed API SHA/size, CRC and specialized guards. Three fresh native resource protocols passed under enforced 2 GiB; four browser viewports cover 320x432, 375x667, 390x844 and desktop with keyboard/touch emulation. [Exact validation and earlier failures](APPLICATION_VALIDATION.md), [patch](candidate.patch), [source](source.json), [method](FEATURE_METHOD.md).

Sleeper-only fantasy projections/results, scoring, legal optimizer, submitted lineups, zero/negative/missing values, exact picks, Neutral/Custom formulas and methods, Trade qualification, saved preferences/goals/rankings, FOIS provenance, account/league isolation and existing restoration/FOIS/Trade admission reserves are preserved. The 2 GiB cap and 16x restoration allowance are unchanged. No production sync, Trade search, FOIS generation, cache clear, restart, credential/infrastructure change or user-data mutation was performed.

The established tooling-only Actions publisher `{controller['commit']}` verified exact evidence and uploaded/read back attachments before merge, then verified the merged tree before immutable publication. Public read-only deployment/readiness/static/auth smokes are separate from fixture and owner-live evidence. Original failures/cancellations remain preserved, not overwritten or counted as passes.

## Independent acceptance

[Complete sanitized Scout prompt](SCOUT_HANDOFF.md). Use existing authorized owner access, preferably a warm compatible context. Stop on admission deferral. Record actual league/week/generation and the precise remaining qualification. Inspect My Team to Market to one eligible exact-player Trade For action and contextual Back without Generate or preference changes. A genuinely provisional state must still withhold the action. Do not infer live recovery, qualified offers or the cause of historical 503s from these fixtures. Physical iPhone/Safari remains untested.
''')
print(json.dumps(dict(written=True,candidate=s['candidate'],tree=s['tree'],deployed=production['commit'],release=release['url'])))
