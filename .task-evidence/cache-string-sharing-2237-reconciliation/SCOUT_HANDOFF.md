# Independent Scout acceptance — build2237 memory reconciliation

Independently review this continuation. Do not implement or trigger heavyweight work to fill missing evidence.

Current baseline: v1.22.22/build2237, commit1e1234fbcf7ca18f3862e5cdeac1451780e51b49, tree4051883efb1f225dcd71e07f1998e45c9d96fb39. No new application change, PR, tag or deployment was made. Customer recovery remains HELD.

1. Verify the current deployed identity and this package's manifest/SHA256 plus downloadable ZIP bytes. Read CORRIGENDUM.md first. The earlier immutable study patched both decoder and digest in candidate mode; do not call its captures decoder-only. Preserve the original release and measurements unchanged.
2. Verify the24new primary result JSONs /12matched pairs. Within each pair, source head/tree, complete fixture bytes, instrumentation hash, digest-helper source and behavior, Python/environment and complete resulting publication digest must agree. Only the loader varies. Check actual2GiB/no-swap/twoCPU/offline controls, no OOM and a new operation kernel peak above setup. Do not use five-ms sampling as the sole peak evidence.
3. Recalculate medians/ranges and inspect per-stage raw/anon/file/inactive-file counters. Peak/retained capture precedes graph accounting. The component graphs are not RSS; standalone and ordered-exclusive groups have different meanings. The raw/normalized catalog dominates the model, not derived actuals. No private Granite structure was profiled, and serialized size does not establish equivalence.
4. Inspect clean lifecycle separately. No graph/digest work precedes cleanup there. Source/history references and workers are released, but residual anonymous memory remains. Scratch unlink removes charged file pages; do not relabel that as anonymous release or proof of leak freedom. Three cycles per control are finite evidence.
5. Review the controlled pressure case: a real deferral followed by explicit known-idle fixture-owner close and real completed restoration. This does not authorize active/pinned production eviction or prove a production victim exists. Review the rejected identity-detachment prototype and decode-only alias bounds without treating them as shipped optimizations or peak savings.
6. New tests are63application-focused plus12comparison-integrity controls. Prior4,250local/4,250hosted, ten gates each and12hosted jobs are reused only for the identical unchanged tree. Their original logs remain in the build2237release; these are not new full-suite runs. Preserve setup/access/earlier incomplete attempts distinctly.

## One fresh authorized admission snapshot

Codex's existing Opera connector returned UNAVAILABLE/not connected. No Render Shell/SSH executor or associated controllable signed-in runtime is available in that session. Main Chat already verified its configured inspection token returned identity200 inside Render; do not repeat that credential check, export tokens or repair the external Cloud binding.

If your existing authorized Render Shell is available, make exactly one metadata-only preflight to the RUNNING application. Do not import a new coordinator/process and treat its state as the serving process.

```python
import json, os
from urllib.error import HTTPError
from urllib.request import Request, urlopen
secret = os.environ.get('DTOS_INSPECTION_AUTH_TOKEN')
if not secret:
    raise SystemExit('Existing configured inspection access absent; stop.')
port = int(os.environ.get('PORT', '10000'))
url = ('http://127.0.0.1:' + str(port)
       + '/api/inspect/operations/restoration-preflight'
       + '?league_id=1314695233040052224')
try:
    with urlopen(Request(url, headers={'X-DTOS-Inspection-Auth': secret}), timeout=5) as response:
        raw = response.read(1024 * 1024 + 1)
except HTTPError as error:
    raise SystemExit('Inspection HTTP ' + str(error.code) + '; stop.')
if len(raw) > 1024 * 1024:
    raise SystemExit('Unexpected response size; stop.')
print(json.dumps(json.loads(raw), indent=2))
```

Record observation/deployment/serving-process identity, current lifecycle and reservations, raw cgroup current/effective limit, anon/file/inactive-file counters, cache size/age/status and exact required capacity/verdict/reason. Process-local idle does not establish all workers idle. File metadata does not prove payload compatibility. The snapshot is advisory/non-atomic and grants no reservation.

Stop on unavailable access, unknown telemetry/inputs or would_defer. Do not poll repeatedly, force a restore, decode a private cache in Shell, clear caches, evict contexts, restart, change settings or lower reserves. The historical35,531,769/670,416,896/702,726,032sample is not a fresh preflight and cannot reconstruct an earlier503.

## One conditional normal entry and actual-score parity

Only if fresh diagnostics permit, use an already signed-in authorized DTOS session for one normal guarded Granite entry. Normal entry must recheck actual admission and compatibility. Stop on deferral. No forced sync, FOIS rebuild, Trade discovery or user-data mutation.

If entry succeeds, verify selected account/franchise, source league, season, scoring, calendar and generation. Read an existing player dossier/Market result; use its actual network request or existing prepared API, retaining the selected franchise rather than guessing a front_office ID. No analytical search should begin merely from navigation.

Choose a supported COMPLETED player-week whose native Sleeper source score is independently visible through an already authorized retained capture or Sleeper view. Compare that exact source score to deployed dossier and prepared Market/API. Pin player identity, league, season/week, scoring fingerprint, source generation, source/retrieval times and qualification. Preserve explicit zero, negatives, precision, missing/conflicting evidence and completed/live distinctions. Do not infer games played or reconstruct a score. Old26.56is a candidate historical capture, not an assumed live answer; projected21.00is not actual-score parity. A dossier agreeing with its own API is not independent source parity. If source corrections/clocks differ, retain that qualification rather than forcing equality through synchronization.

Report separate PASS/PARTIAL/HELD for measurement integrity, unchanged mandatory-source validation, resource/cleanup evidence, fresh live admission, actual entry and independent native-score parity. A successful entry alone does not prove a cleanup/decoder change caused recovery. Do not claim Granite recovery or the earlier503cause from fixtures or this diagnostic study.
