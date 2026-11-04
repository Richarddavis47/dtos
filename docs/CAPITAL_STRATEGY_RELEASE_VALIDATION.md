# Capital + strategy reconciliation release preparation

## Candidate and main reconciliation

The accepted local implementation remains commit `4c3734c` on
`fix/capital-strategy-reconciliation`. Main was fetched twice during release
preparation on 2026-10-05 and remains
`7e6bd6e383d72a573398feb1aece55dd71005694`. No intervening changes or conflicts
require reconciliation. Storage and sparse-history branches were not changed.

The proposed release is **v1.21.6 / build 2106**, with centralized metadata and
public notes for Trade Center Capital + Strategy Reconciliation. These release
preparation edits remain local until required release validation passes.
The subsequent lifecycle reconciliation below supersedes the initial blocked
status; the original failures are retained as historical validation evidence.

## Product contract

The focused acceptance suite preserves separate Market value, current optimal
legal-lineup production, priced future capital, strategy fit and counterparty
plausibility. Strategy changes neither canonical Market prices nor lineup
observations. Picks receive no projected weekly points, and supported weekly
observations are counted once across overlapping horizons.

Win Now can spend capital for material legal-lineup improvement; Rebuild can
sacrifice current production for meaningful priced capital; Retool can qualify
balanced exchanges. Ownership, exact identity, duplicates and unresolved
capacity remain independent constraints. Truly missing required evidence stays
unresolved. Supported costs are disclosed.

All five recommendation labels are covered. Both managers have separate
material benefit/cost assessments. A fourth-round return for an elite asset
fails; a tiny positive signal cannot erase large losses. Missing FOIS is a
limitation rather than an automatic veto; no acceptance probability is invented.

Create Trade, Recommended Trades, Shop Asset, Shop Draft Capital, Trade For and
adjustments retain shared evaluation. Release preparation extends the existing
real-evaluator fixture to prove alternatives also retain explicit strategy and
exactly match direct evaluation. All six A–F package families remain covered.
Exact acquired-pick year, round, original franchise, current owner, projected
range and confidence remain intact, including explicit unknown ranges.

## Initial validation and release blocker

- Focused capital/workflow/API/browser suite: **171 tests passed**.
- Linux lifecycle/tooling unit contracts: **74 tests passed**.
- Docker, 2 GiB / two CPUs: maintenance/quiescence checks passed; **141 recovery tests passed**.
- Initial full regression: 2,409 cases ran; one Market memory-budget test deferred
  work during a concurrent Docker build. Its isolated rerun passed without
  changing the gate or memory limits. A second full run encountered 93 errors
  and three failures while retained disposable lifecycle fixtures kept the
  worker above the unchanged memory-admission ceiling. Those fixture files
  were removed; failure logs and the ordinary lifecycle summary were preserved.
  Memory admission then passed again. The final canonical run passed after
  cleanup, without concurrent containers or builds.
- Final full regression: **2,409 tests passed**; the canonical test gate took
  219.264 seconds. Browser contracts used system Chromium 151.0.7922.173.
- Final canonical release validation: **all 10 gates passed** in 238.294 seconds,
  including authoritative Ruff, compilation, dependency integrity and whitespace.
- Routes/OpenAPI passed: 257 method registrations, no duplicates, 236 paths.
  Tracked HTTP validation and final process cleanup passed; no genuine DTOS
  Python/Uvicorn server or validation container remains active.
- Required ordinary Docker lifecycle: **failed**, exit 1. The unchanged gate
  asserts `expected exactly one semantic child, got 6` during replacement
  warming; the saved summary reports phase `nonsemantic_reuse`.
- Required archive-warmed and combined-read fixture generation: **failed**,
  exit 137 with OOM events under the unchanged 2 GiB limit. The archive-warmed
  retry also exited 137. Neither scenario reached a passing lifecycle summary.

These failures are retained as release blockers. No gate, fixture scale, memory
limit, storage implementation or lifecycle implementation was weakened or
modified. Docker dependency installation used the Cloud proxy configuration
and a temporary CA secret mount with TLS verification enabled; the repository
Dockerfile is unchanged. Fixtures are disposable local generated data, not
production evidence.

Release publication was stopped while required Linux lifecycle validation was
red. No merge, tag or production deployment is authorized in this task.

## Three-way lifecycle reconciliation

Before making a correction, frozen snapshots of clean main `7e6bd6e`, capital
implementation `4c3734c` without preparation edits, and the full prepared
candidate were run with equivalent full-scale fixtures, generator commands,
archive flags, 2 GiB memory/swap limits and two CPUs. A second matrix reproduced
the original concurrent scenario launch pattern with private observational
process and subprocess-result tracing. Source manifests confirmed the capital
implementation remained unchanged; generator, gate and Market engine source
were identical across all three revisions.

| Snapshot | Ordinary, sequential / concurrent | Archive-warmed | Combined-read |
| --- | --- | --- | --- |
| A: clean main | publication failure / pass | generator OOM, exit 137 | generator OOM, exit 137 |
| B: capital implementation | pass / seven-attempt failure | generator OOM, exit 137 | generator OOM, exit 137 |
| C: prepared candidate | pass / six-attempt publication failure | generator OOM, exit 137 | generator OOM, exit 137 |

Each production-shaped failed run recorded an OOM kill before application
startup. At the 2 GiB peak, approximately 1.9 GiB was nonreclaimable tmpfs file
memory: the generated archive database plus WAL. Generator RSS was approximately
145 MiB; no Uvicorn, Projection, FOIS, Market or browser worker was running when
the generator was killed. Inline fixture Projection seeding had already finished.

The six C replacement children were sequential invocations of
`src.core.asset_market.semantic_worker` parented by the same Uvicorn process.
Each exited zero and was reaped, with the same request-generation identity.
They were neither duplicated Uvicorn workers nor misclassified browser,
validator, fixture or orphan processes. After successful semantic preparation,
artifact construction repeatedly failed the unchanged memory-admission target
because tmpfs artifact bytes were also nonreclaimable working-set memory.
Retry timing explains the varying cumulative child count and whether publication
eventually succeeds. Detailed PID/PPID, command, result, ordering, memory,
archive and cleanup evidence remains private outside the repository.

Classification: **E, validation fixture-placement defect**, with **F, ordinary
resource-condition variation**. There is no capital/strategy or release-metadata
regression, no process-detector misclassification, and no application-RSS OOM.
Private function tracing recorded no capital assessment or Trade Center
evaluation/discovery calls on the failing lifecycle paths.

## Smallest correction and unchanged-contract proof

The prior local execution mounted production-shaped fixtures from `/tmp`, which
is tmpfs on this Cloud worker. Repository CI uses disk-backed `.validation/`
directories. Corrected local execution uses disposable disk-backed directories
under `/workspace`, with the same frozen candidate and all generator, archive,
workload and resource settings unchanged. `docs/VALIDATION.md` documents this
requirement. No production implementation, generator, lifecycle gate, memory
threshold, expected child count or fixture scale was changed.

All three corrected full-scale lifecycle scenarios passed. Each recorded exactly
one replacement semantic child, zero OOM/OOM-kill/group-kill events, two controlled
restart cycles, graceful Uvicorn shutdown and no remaining application processes.
All validation containers were removed and disposable fixture files cleaned up.

| Scenario | Raw peak bytes | Effective peak bytes | Effective margin bytes | OOM kills |
| --- | ---: | ---: | ---: | ---: |
| Ordinary | 1,502,572,544 | 1,408,421,888 | 739,061,760 | 0 |
| Archive-warmed | 2,147,483,648 | 1,397,153,792 | 750,329,856 | 0 |
| Combined-read | 2,147,483,648 | 1,402,003,456 | 745,480,192 | 0 |

The production-shaped runs reached the raw limit during fixture/page-cache
activity with successful kernel reclamation and zero OOMs. Effective peaks and
required margins remained within the unchanged lifecycle contract. Full
production-shaped record counts and archive pressure checks were preserved.

After reconciliation, the capital/workflow/API/browser suite passed again:
**171 tests**. Lifecycle, replacement-window, process-cleanup and cache-budget
contracts passed: **100 tests**. Their initial concurrent host run encountered
two memory-admission deferrals; a serial rerun after disposable-input cleanup
and non-destructive reclamation of unused diagnostic file cache passed. The
comparison snapshots and all failed-run evidence were retained privately.
Authoritative Ruff, compilation and whitespace passed without gate changes.

Publication requires the canonical release validator to pass on the final
release source before push/PR. Green required CI and conflict-free current main
are required before a separately authorized merge. This task stops before merge,
tagging or deployment.
