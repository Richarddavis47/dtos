from pathlib import Path
import json
b=Path('/workspace/2245-recommended-protections');s=json.loads((b/'source.json').read_text());local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text());proof=json.loads((b/'focused-resource-verified.json').read_text())
assert local['all_local_gates_passed'] and host['all_gates_passed'] and proof['all_native_guards_passed'];assert local['candidate']==host['candidate']==proof['candidate']==s['candidate'];assert local['tree']==host['tree']==proof['tree']==s['tree'];assert local['tests']==host['tests']==4346
text=f'''# Recommended Trades: temporary exact outgoing protections

## Release review outcome

Candidate `{s['candidate']}`, tree `{s['tree']}`, PR #334, target DTOS v1.22.30 / build 2245. Baseline `{s['baseline']}` was ready at v1.22.29/build2244. This sealed report records validated source before publication; consult the separate final publication/production receipts for actual merge and deployment. It does not claim release merely from passing tests.

## Confirmed gap and smallest correction

A real authenticated 320×432 disposable replay of baseline had no usable Recommended Trades pre-search asset protection picker. The native search already supported exact `protected_assets`, including discovery/construction filtering, while Shop/adjustment had legacy draft controls. The correction exposes that existing constraint through temporary Recommended-only controls; no generator, evaluator, price, projection, qualification threshold or memory policy changes.

Before explicit Generate, open “Protect assets & options”, choose owned players or exact picks and add/remove/clear them. Count and chosen exact assets remain visible outside the disclosure. Picks retain year, round, original franchise and exact ID. Own2029first (`2029-R1-1`) is not acquired2029first (`2029-R1-3`). Workspace restoration checks current owned IDs in the existing authorized account/league/franchise scope. Storage does not authorize an asset; native ownership/source/resource checks remain authoritative.

Recommended-only temporary state is distinct from Evaluate/Shop constraints. No permanent preference write occurs. Existing saved Custom Protect flags continue through the native merge; clearing temporary selections does not erase saved flags. The Evaluate draft, ordered assets, selected comparison offers, valuation mode and strategy retain existing behavior. Control edits start no search, sync, provider fetch or history work. League switching clears stale cross-scope context.

A completed search retains the effective exact protection snapshot returned by the server. Current or separately disclosed earlier results show their own settings, never newly edited controls. Legacy snapshots that lack settings remain unknown. A completed zero-qualified search remains distinct from deferral/failure; restrictions are shown with “Protections limit outgoing assets; they do not explain a trade’s verdict.” No claim is made that restrictions caused rejection.

## Native fixture acceptance

Focused final-source command completed16tests; separate retained history/partner/team-need/comparison browser controls completed15, and a separate native Win Now/Neutral control completed1. Counts are executions, not independent unique coverage or owner live offers. The same new4native browser tests are also included in full regression and hosted Product.

The native search spy observed36actual outgoing construction pools. Exact protected ownfirst/player were excluded throughout; the other same-round first remained eligible. Three real returned exploratory assessments respected all exclusions;0qualified is an acceptable fixture result. A separate all-owned-protected native search completed with no offers and truthful applied settings. Actual Evaluate ran twice without Recommended-only constraints. Clearing/editing/reload/contextual Back, ordered draft/comparison preservation and league isolation are asserted. No seeded recommendation or bypassed admission is used.

Four phone/desktop captures:320×432,375×667,390×844,1280×900. Keyboard focus,44pxremove targets,touch emulation,wrapping and original Generate reachability controls passed. Existing375/390/400×677 proposal-tray assertions are unchanged. The initial extra disclosure row obstructed Generate and was removed by reusing the existing disclosure; original failures and reproductions remain preserved.

## Complete mandatory evidence

- Local Python3.14.3:4,346tests, all10canonical gates, enforced2GiB/no extra swap,2CPUs,network-none,UID1000. Original manifest `{local['local_manifest_entries']}` entries verified byte-for-byte. Elapsed{local['elapsed_seconds']:.3f}s; whole-validation kernel peak{local['kernel_peak']}bytes. This is not incremental Trade demand or production spare capacity.
- Hosted canonical run42870745631:4,346tests/all10gates,658original manifest entries,2GiB,elapsed4375.241s. Original archive83,468,084bytes, SHA256`3978cb1ab26898f12104faae4490ceb949311ec5040b713e19be1f3a42d475af`.
- All13required hosted jobs on the exact source passed, including Product847(673+35+139), separate Welcome/security412,My Team,beginner navigation,historical timeline,projection cross-version,resident refresh,Ubuntu/Windows tooling,and three Linux lifecycle modes. Optional legacy2191publisher is skipped, not a required gate.
- All15native hosted ZIPs match API sizes/digests, ZIP CRC, exact source and applicable native guards. Existing enforced memory/deferral/recovery/cancellation/timeout/cleanup/resource-preflight/history/actual-results guards remain required and passed. Intentional pressure cases are not completed-worker passes.
- Frozen Actions publisher:79integrity unit tests,ruff/compile checks; canonical steps identical to application workflow,contents:write confined to established publisher. Controller is not merged into production. Native prepare must verify all attachments before the expected-head PR merge; publish must require the same validated tree on main and immutable source/attachment checks. No direct Cloud upload credential is used.

Original full consoles, tests/gate traces, cgroup samples, manifests and byte-preserving <=60,000byte UTF-8 parts are accessible through the final handoff. Method scripts and runtime image/freeze/limits are retained. Source patch is exactly baseline→candidate. Every previous failed/canceled/incomplete attempt is separate; see PRIOR_ATTEMPTS.md, the prior archive and fixed public original URLs.

The first final-source local attempt timed out at the external80minute budget after3,998completed/3,999started tests. It is incomplete, not a pass. Cleanup confirmed0active descendants and noOOM. The same source completed with only the local external budget extended to110minutes; official CLI, all tests/gates, production timeouts, reserves,2GiB and hosted workflows were unchanged. Passing hosted workflows were not rerun for this local orchestration limitation.

## Preserved contracts and limits

No backend `src/`,services or routes changed. Canonical Neutral/Custom prices and rank-slot methods, exact picks, Sleeper-only projections/actuals, scoring, analytical versus submitted lineups, bilateral thresholds, FOIS provenance, generation guards,2GiB,Trade256+128MiB and FOIS768MiB remain unchanged. No production search,sync,FOIS rebuild,restart,cache clear or user-data write was performed. Fixture preference equality is evidence about disposable state, not an authenticated inspection of the owner's account.

The associated owner Browser capability is not available in this session. No owner authenticated live offer acceptance, live production capacity claim or physical Safari acceptance is made. After release, public readiness/static byte identity and guest authentication boundaries may be verified without league hydration. Independent Scout may perform one explicit guarded live search only when safe capacity and authorized session exist; stop on deferral. Full prompt:SCOUT_HANDOFF.md.
'''
# Space generated prose only; original evidence is never edited.
for old,new in [('build2244','build 2244'),('Own2029first','Own 2029 first'),('acquired2029first','acquired 2029 first'),('completed16tests','completed 16 tests'),('completed15','completed 15'),('completed1.','completed 1.'),('new4native','new 4 native'),('observed36actual','observed 36 actual'),(';0qualified','; 0 qualified'),('ran twice','ran twice'),('targets,touch','targets, touch'),('captures:320','captures: 320'),(':4,346tests',': 4,346 tests'),('all10','all 10'),('all13','all 13'),('All13','All 13'),('All15','All 15'),('Product847','Product 847'),('Welcome/security412','Welcome/security 412'),('publisher:79','publisher: 79'),('<=60,000byte','<=60,000 byte'),('of the owner','of the owner'),('after3,998','after 3,998'),('confirmed0active','confirmed 0 active'),('noOOM','no OOM')]:text=text.replace(old,new)
(b/'REPORT.md').write_text(text);print('Wrote release-review report from verified final local+hosted evidence; deployment still requires native publisher.')
