"""Append verified actual release/deployment receipts; preserve earlier originals."""
from pathlib import Path
import datetime
import hashlib
import json
import re
import subprocess

B = Path(__file__).resolve().parent
E = Path('/workspace/cache-sharing-handoff')
prefix = Path('.task-evidence/franchise-progress-2250')
T = E / prefix
s = json.loads((B / 'source.json').read_text())
m = json.loads((B / 'merge-verified.json').read_text())
p = json.loads((B / 'production-verified.json').read_text())
certificate = json.loads((B / 'publish-certificate-verified.json').read_text())
assert certificate['passed'] and certificate['main'] == m['merge_commit'] == p['commit']
assert p['passed'] and p['build'] == s['build'] and p['tree'] == m['tree'] == s['tree']
repo = 'repos/Richarddavis47/dtos'
release = json.loads(subprocess.check_output(['gh', 'api', repo + '/releases/443455874'], text=True))
tag = json.loads(subprocess.check_output(['gh', 'api', repo + '/git/ref/tags/v' + s['version']], text=True))
assert release['immutable'] and not release['draft'] and release['target_commitish'] == m['merge_commit']
assert tag['object']['type'] == 'commit' and tag['object']['sha'] == m['merge_commit']
assets = [{k: row.get(k) for k in ('id', 'name', 'size', 'digest', 'browser_download_url')}
          for row in release['assets']]
assert len(assets) == 23
identity = dict(source=s, merge=m, deployed=p, release={
    k: release.get(k) for k in ('id', 'tag_name', 'target_commitish', 'draft', 'immutable',
                              'published_at', 'html_url', 'name')},
    tag=dict(ref=tag['ref'], type=tag['object']['type'], sha=tag['object']['sha']),
    attachments=assets, checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    no_production_user_data_or_settings_mutations=True,
    authenticated_live_acceptance=False,
    authenticated_limit='No supported authenticated owner browser or Render Shell was available in this session. Existing external401 binding was not retried. No cold entry was forced.')
(B / 'final-release-and-deployment.json').write_text(json.dumps(identity, indent=2) + '\n')


def write(name, raw):
    path = T / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        assert path.read_bytes() == raw, 'Preserve existing evidence: ' + name
    else:
        path.write_bytes(raw)


names = ['final-release-and-deployment.json', 'merge-verified.json',
    'prepare-certificate-verified.json', 'publish-certificate-verified.json',
    'prepare-certificate-original.zip', 'publish-certificate-original.zip',
    'prepare-certificate-original.zip.delivery.json', 'publish-certificate-original.zip.delivery.json',
    'prepare-certificate-verification-original.log', 'publish-certificate-verification-original.log',
    'prepare-artifact-metadata.json', 'publish-artifact-metadata.json',
    'publisher-prepare-final.json', 'publisher-publish-final.json',
    'publisher-prepare-jobs-original.json', 'publisher-publish-jobs-original.json',
    'publisher-prepare-collection-original.log', 'publisher-publish-collection-original.log',
    'publisher-hosted-controls-verified.json', 'publisher-publish-started.json',
    'production-render-verified.json', 'production-smoke-original.json',
    'production-verified.json', 'production-history-auth-boundary.json',
    'production-smoke-verification-original.log', 'deployment-readiness-sample.json',
    'post-release-source-cleanup.json', 'prepublication-evidence-published.json',
    'recovery-verified.json', 'prior-package-final-complete.json']
for name in names:
    write('publication/' + name, (B / name).read_bytes())
for folder in ['prepare-certificate-native', 'publish-certificate-native']:
    for path in sorted((B / folder).rglob('*')):
        if path.is_file():
            write('publication/' + folder + '/' + str(path.relative_to(B / folder)), path.read_bytes())
write('publication/methods/' + Path(__file__).name, Path(__file__).read_bytes())
outcome = f'''# Released and deployed — DTOS v{s['version']} / build{s['build']}

PR339 merged with an expected-head safeguard. Actual main/deployed commit:
`{m['merge_commit']}`. Validated candidate:`{s['candidate']}`.
Both have source tree:`{s['tree']}`.

Immutable release: {release['html_url']}
Release ID443455874 has23attachments; API digests, manifests, certificateCRC and
Actions full byte readback were verified before/after publication.
Publisher:`26d54f1277fa719f5e32c5219e2dcdfb878967a6` (never merged).
Prepare run43298245909; publish run43299014514; both passed141publishercontrols.
Render deployment `dep-dbr1u4vf3r2c73bqno4g` islive, matching main exactly.
Readiness reportsready/v{s['version']}/build{s['build']}; seven bounded public
smokes plus the separate private-history authentication-boundary check passed.
These are not owner-authenticated franchise acceptance.

Local and hosted canonical each passed4435tests/allten gates. All13required
hosted jobs passed. Product932, focused103, three native2GiB protocols and the
required supplemental two-method browser capture passed. Original manifests:
746local/750hostedentries, allbytes verified. The supplemental capture did not
change the original canonical manifest. Both full runs reached the2GiB cap with
zeroOOM/oomkill; the local periodic observer ended21.03minutes before completion
atits10000row bound. See the exact resource and source records; no continuous
profiling/long-term leak-freedom claim is made.

Franchise History extends its existing card with source-season selection, gross
player/pick acquisitions/disposals, observed net transfers, exact original-pick
identities and supporting trade/conversion links. The partial retained Day sample
has2completedtrades, players1acquired/3sent(net−2), picks5acquired/2sent(net+3).
This is observed trade movement, not total roster change, current holdings or
proof of improvement. The pick converted toplayer13346 is not another trade
acquisition. Sparse Arkham history remainsunknown. These are retained replay and
disposable controls, not fresh owner live counts.

The GC precondition occurs before fixture construction; an AST receipt confirms
the original workload/timing/heartbeat/500ms/shutdown statements are unchanged,
with GC enabled and actual two-record completion asserted. The original542.77ms
failure's cause remainsunproven. The940075-object collection followed both the
prefix and its first worker; allocation origins were not attributed. Earlier
over-specific interpretation is qualified inFOIS_FIXTURE_REVIEW.md, with original
records unchanged. All earlier failed, interrupted, cancelled and invalid
diagnostic/harness attempts remain distinct inPRIOR_ATTEMPTS.md and checkpoints.

No Trade/FOIS grades, valuation/scoring/Sleeper source rules, ownership guards,
memory policies, preferences, rankings, lineups, user data or infrastructure were
changed. Physical iPhone/Safari and authenticated owner acceptance remainunverified.
Use [the final Scout prompt](SCOUT_ACCEPTANCE.md), [readable originals](README.md),
[publication/deployment receipt](publication/final-release-and-deployment.json),
andthe release'sevidence-manifest.json/SHA256SUMS. Earlier README snapshots retain
their original prepublication timing; this outcome supplies actual final identity.
'''
write('RELEASE_OUTCOME.md', outcome.encode())
prompt = f'''# Scout — independent acceptance of Franchise Progress

Production:v{s['version']} / build{s['build']}.
Deployed/tag/main:`{m['merge_commit']}`.
Validated candidate:`{s['candidate']}`; exact shared tree:`{s['tree']}`.
PR:https://github.com/Richarddavis47/dtos/pull/339
Immutable release:{release['html_url']}
Publisher26d54f1277fa719f5e32c5219e2dcdfb878967a6;
prepare43298245909/publish43299014514. No owner live verification is claimed.

1. Independently verify the immutable tag/main/deployed tree, readiness and all23
   attachments. Reconcile release evidence-manifest.json andSHA256SUMS with the
   certificate/API digests. Review original local/hosted consoles and tests.jsonl
   in60KBparts, manifests746/750entries,4435methods/allten gates each,13required
   hostedjobs,Product932,focused103 and native2GiB lifecycle receipts. The two
   publisher jobs also ran141realcontrols each. The legacy2191job was inapplicable
   and skipped; it is not amongthe13requiredapplicationjobs.
2. ReadFOIS_FIXTURE_REVIEW.md andPRIOR_ATTEMPTS.md. Preserve the original542.77ms
   local failure, deliberate remainder interruption, old-head hosted cancellation,
   invalid diagnostic prototypes and external spawn-harness errors. No original
   causal diagnosis or continuous full-runtime memory sample is claimed. Confirm
   allunchangedbenchmarkwork remains, enabledGC/500ms/real completion/cleanup.
3. Use existing authorized owner access. Keep inspection credentials insideRender;
   preferGitHubforRender signin. Do not repeat the external401method or credential
   check MainChat already completed. If a league is cold or capacity uncertain,
   use the existing Render-local running-process preflight and respect fresh
   admission. Stop ondeferral. Do not force sync/backfill/FOIS/search/cacheclear/
   restart, alter settings or execute transactions.
4. Inan already supported authorized league/franchise, open existing Franchise
   History. Select a retained source season; note its coverage and events page.
   Reconcile one displayed completed-trade/gross-movement summary with supporting
   completed source events, across pagination. Do not substitute today's owners,
   prices, scoring or manager identity. Owner leagues are samples, not code limits.
5. Check a repeated asset acquired then sent: both events mustremain in gross
   directions; net is within observed trades only. Verify exact picks byyear,
   roundandoriginalfranchise; same-round picks fromdifferentfranchisesstaydistinct,
   own-originpicks are identifiable. Source-season/configuration mustmatch.
6. Open asupporting completedtrade, follow an existing subsequentmovement or exact
   pickconversion onlywhen supported, thenreturn viaoriginaltrade/contextualBack.
   Preserve source-season filter, pagination andreload context. A convertedpick
   isnot countedagainasanunrelated player acquisition; package links do not imply
   one-to-one consideration. Trade drafts/comparisons/preferences remainuntouched.
7. Inspect partial/missing/complete-empty periods and incomplete consideration.
   Missing remainsunknown; zeroempty activity requires complete compatible source
   coverage and franchisecontinuity. Independent supported player/pick facts remain
   visible; affected netswithheld. Exclude pending/rejected/cancelled/failed,
   correctionsandwaivers fromcompleted trades; deduplicateevents. Unknown dates
   andmanagerchanges stayqualified. Beginning/end inventoriesarewithheld unless
   real snapshots supportthem. Other roster activity remainsseparate.
8. Verify account/league switching clears stale context. Test another supported
   league when prepared access permits; do not infer current managerialintent,
   improvedfranchisequality, hindsightvalueorchampionshipcredit. FOIS remains
   RETAINED / NOTREVALIDATED. No source/providerpreparation occurs fromsummary,
   filteringordisclosure. Preserve neutral/custom andSleeper-only fantasy rules.
9. At320×432,375×667,390×844anddesktop checkreadability, keyboardfocus, touch,
   exactidentity details, links, overflowandBack. Recorded acceptanceisChromium
   emulation, notphysicaliPhone/Safari. Report actual physicaltesting separately.

Reference only: frozen partial Day Traders source-season2026,source roster4:
2trades;players1in/3out;picks5in/2out. Root1333655835015942144,
later1414718106177122304;PICK-2026-R2-ORIG7 converts toplayer13346.
FixtureSHA012de53aeefa4cfb4cb7de717910fa829f399b23d6f6ad7962598afe8c76833f.
These are retained replay, not assumed current owner counts. Granite-shaped1QB/
K/DEF andSuperflex are disposable preservation controls, not new live recovery.

ReportPASS/PARTIAL/HELD per evidence family. Distinguish fixtures, retainedreplay,
sourceinspection, publicdeploymentchecks and actual authenticated observations.
Do notlabelthefranchise improved or declareGranite recovery fromfixture success.
'''
write('SCOUT_ACCEPTANCE.md', prompt.encode())
token = re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|[?&]sig=[A-Za-z0-9%+/]{16,})')
rows = []
for path in sorted(T.rglob('*')):
    if not path.is_file():
        continue
    assert not path.is_symlink()
    if path.name in {'manifest-final.json', 'SHA256SUMS-final'} and path.parent == T:
        continue
    raw = path.read_bytes()
    if path.suffix in {'.md', '.json', '.jsonl', '.log', '.txt', '.py', '.patch'}:
        assert not token.search(raw), str(path)
    rows.append(dict(path=str(path.relative_to(T)), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
write('manifest-final.json', (json.dumps(dict(source=s, deployed=m['merge_commit'],
    status='RELEASED_IMMUTABLE_DEPLOYED_PUBLIC_SMOKES_PASS_OWNER_LIVE_UNVERIFIED',
    observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), files=rows), indent=2) + '\n').encode())
write('SHA256SUMS-final', ''.join(row['sha256'] + '  ' + row['path'] + '\n' for row in rows).encode())
subprocess.run(['git', '-c', 'core.autocrlf=false', 'add', '-f', '--sparse', '--', str(prefix)], cwd=E, check=True)
index = {}
for entry in subprocess.check_output(['git', 'ls-files', '-s', '-z', '--', str(prefix)], cwd=E).split(b'\0'):
    if entry:
        info, path = entry.split(b'\t')
        index[path.decode()] = info.split()[1].decode()
for path in T.rglob('*'):
    if path.is_file():
        raw = path.read_bytes()
        assert index[str(path.relative_to(E))] == hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
subprocess.run(['git', 'commit', '-m', 'Record immutable2250 release, actual deployment and final Scout acceptance'], cwd=E, check=True)
subprocess.run(['git', 'push', 'origin', 'HEAD'], cwd=E, check=True)
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=E, text=True).strip()
branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=E, text=True).strip()
assert subprocess.check_output(['git', 'ls-remote', 'origin', 'refs/heads/' + branch], cwd=E, text=True).split()[0] == commit
receipt = dict(source=s, deployed=m['merge_commit'], tree=s['tree'], commit=commit,
    url='https://github.com/Richarddavis47/dtos/tree/' + commit + '/' + str(prefix),
    scout_url='https://github.com/Richarddavis47/dtos/blob/' + commit + '/' + str(prefix) + '/SCOUT_ACCEPTANCE.md',
    manifest_sha256=hashlib.sha256((T / 'manifest-final.json').read_bytes()).hexdigest(),
    files=len(rows), staged_git_blob_bytes_verified=True, remote_commit_verified=True,
    immutable_release=release['html_url'], public_production_verified=True,
    owner_authenticated_acceptance=False)
(B / 'final-evidence-published.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
