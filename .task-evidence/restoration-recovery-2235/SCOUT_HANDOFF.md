# Independent acceptance: bounded restoration recovery, build 2235

Application candidate `5d9c885fcc7e25d6e43fc9c759bc6349c6004da8`, tree `7b2dd610add3a536ba1112f92943ae5ccff5999c`; PR324. Baseline v1.22.19/build2234, `9c1886c40c9697da0be3b5f06ede0bf9f45f4682`. Planned release v1.22.20/build2235. Verify the final publication certificate, immutable release tag and production readiness for actual merged/deployed identity. Publisher/evidence trees are separate from the application tree. This is an acceptance prompt, not independent approval.

1. Verify every mandatory final-source job, both original canonical test consoles, test start/stop counts, all ten gate completions, both canonical manifests, release checksums and original artifact integrity. Read failures separately. The baseline comparison deliberately reaches HeavyWorkDeferred; it is not a completed worker or a final candidate failure. Readable log chunks must concatenate to original full-console hashes.
2. Inspect the narrow production diff. Restoration performs one existing bounded cleanup only for measured insufficient headroom with its safety margin still present, retains the same lease/opened generation, then reruns the exact unchanged guard against fresh raw cgroup memory and FOIS ownership. Counts/inactive-file pages cannot substitute for measured headroom. Unknown/unsafe conditions still defer. Fresh/caller-held contexts and active runtimes must survive. No threshold or16× allowance is lowered; FOIS768MiB and Trade256+128MiB policies remain unchanged.
3. Review the enforced2GiB/no-swap/offline acceptance. Require actual restore/publication, unexpired-pressure deferral, explicit recovery, active FOIS reservation protection, actual worker exit and scratch cleanup. Existing Trade/FOIS controls must prove real completion, cancellation and timeout independently of deferral. Review six same-process cycles and stage counters; do not call short-cycle stability long-term leak freedom. The recovery tool's whole-operation peak above its post-cleanup level includes pre-cleanup memory; use the separate cycle profiling for sampled restoration-only increments.
4. Review fixture/source controls for cache identity, atomic replacement, compatible1QB/FLEX/K/DEF versus Superflex scoring, eviction/reopening, failed/unknown telemetry, owned-reader cancellation, exact picks, native Sleeper zero/negative values, and account boundaries. The sealed old synthetic input is not private Granite's payload; byte size does not establish equivalent demand. Do not infer production ownership from synthetic expired contexts.

## One bounded production preflight through existing authorized Render-local access

Use the already authorized Render Shell. Do not print/export the configured inspection token or run an identity check merely to repeat the already completed credential verification. The following request goes to the existing running application, not a new lifecycle coordinator. It performs no hydration, private payload decode, provider acquisition or heavyweight lease:

```python
import json, os
from urllib.request import Request, urlopen
port = os.environ.get('PORT', '10000')
request = Request(
    f'http://127.0.0.1:{port}/api/inspect/operations/restoration-preflight?league_id=1314695233040052224',
    headers={'X-DTOS-Inspection-Auth': os.environ['DTOS_INSPECTION_AUTH_TOKEN'],
             'Cache-Control': 'no-cache'})
with urlopen(request, timeout=8) as response:
    assert response.status == 200
    body = response.read(262145)
assert len(body) <= 262144
print(json.dumps(json.loads(body), indent=2))
```

Do not print request headers, environment values, raw exceptions or private cache contents. If the existing request fails, retain only its status and stop; do not rotate credentials, repair the external binding, proxy or repeatedly probe.

Record current observation/process/deployment identity, actual cache metadata, raw container memory/effective limit, outstanding process-local ownership/reservations and admission reason. Distinguish serving-process activity from container-wide memory and other workers' unknown state. This advisory non-atomic snapshot grants no reservation and cannot reconstruct an older503. Current metadata does not establish payload compatibility.

## Conditional normal entry and outstanding live Sleeper parity

Only if fresh evidence supports safe normal entry, use the owner's existing signed-in browser and enter Granite once through normal navigation. Normal entry must recheck admission and compatibility. Do not bypass a deferral or force source preparation. No Trade recommendation search is authorized by this task. Record success, capacity deferral, incompatibility or unavailable session separately. A successful disposable restore is not live Granite recovery.

If entry completes, choose one actually supported completed player-week and compare its retained explicit Sleeper individual source value with the deployed dossier and matching prepared consumer. Pin league, season, week, player identity, scoring context, compatible generation and observation/freshness qualification. Authority should remain `sleeper-matchup-actuals-v1`. Keep player-map and ordered-starter conflicts withheld; team custom-point adjustments are not individual scores. API precision must match the admitted value; display follows the established two-decimal convention. Do not assume the older26.56 replay,183.82 total, a current-season average or a different scoring league proves this live match. If evidence is absent, conflicting, stale/incompatible or inaccessible, report that boundary without manufacturing a score or triggering sync.

Check normal Home/My Team/Market/Trade navigation and restored workspace context only where already safe. Do not change rankings, valuation method, goals, lineups, trades or preferences. No forced sync, FOIS rebuild, cache clearing, restart, active-context eviction, infrastructure change or credential export. Keep fixture/source evidence, public readiness and authenticated live observations separate. Chromium phone emulation is not physical iPhone/Safari acceptance.

Shipping this recovery path does not establish Granite recovery, actual private cache peak, the cause of an earlier503 or live Sleeper parity. If this session lacks the required authorized browser/Shell access, live acceptance remains HELD; do not substitute an external401 retry or a separate process's idle coordinator.
