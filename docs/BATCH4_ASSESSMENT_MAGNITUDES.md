# Batch 4 real decision-assessment replay

## Transfer and provenance

The single authorized encrypted Wormhole transfer completed. ZIP size: 472,523
bytes; SHA-256: `45f2af23af87344888ece78173deaee834e7609ce0a04b09b6d314dae4a1cafe`.
Export used standalone standard-library code with SQLite `mode=ro`,
`query_only=ON` and a read transaction. No candidate application imports ran on
Render. No production database/schema/application mutations occurred.

Exported 1,536 relevant global Market observations, 1,237 Day Traders checkpoints
and 1,237 references. Five existing local season archives matched the exported
production semantic checksums. No archive payload was retransferred.
The remote `/tmp/dtos-batch4-assessments.zip` was deleted immediately after local
checksum verification; the shell confirmed absence. No helper file, SSH key,
endpoint, service or job was created. Sender confirmed transfer completion.
The one-time code is not retained in this report.

Local ZIP, replay database and derived assessment panel remain in ignored
`.validation/batch4-assessment-transfer` only for dependent Batch 4 calibration.
Delete these after that work completes; it is intentionally not complete yet.

## Concrete defect exposed by actual magnitudes

The first replay reproduced Richard's 4/73/5 E/P/I coverage and retained actual
classifications: 14 strong, 2 sound, 36 defensible, 5 questionable, 20 poor,
5 insufficient. These were evaluator outputs, NOT accepted manager quality.
All 20 poor classifications and 12 of 14 strong classifications involved
incomplete Market packages. The evaluator compared priced subsets as though
they established full-package fairness. Excluding unpriced assets from a sum
does not make the resulting ratio a complete package comparison.

Corrected that defect: fairness is unavailable when any package asset lacks
contemporaneous price. The ratio-based overall process classification is also
unavailable. Independently supported dimensions survive as scoped partial
evidence, without receiving a substitute score. Methodology:
`historical-trade-process-outcome-2`.

## Corrected real Trading assessment magnitudes

Numbers below are existing evaluator magnitudes on its 0–100 process scale,
not FOIS category grades. They are classification mappings, not continuous
measurements. No arithmetic manager-grade average has been applied.

| Manager | 90 strong | 80 sound | 65 defensible | 40 questionable | 20 poor | Scalar unavailable |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| RichardDavis47 | 2 | 1 | 7 | 0 | 0 | 72 |
| danreilley | 3 | 0 | 7 | 0 | 0 | 53 |
| davefedex | 3 | 2 | 13 | 1 | 2 | 95 |
| garrettadame36 | 0 | 0 | 6 | 0 | 0 | 19 |
| Mears30 | 1 | 1 | 0 | 0 | 0 | 26 |
| zkobes | 0 | 1 | 2 | 0 | 0 | 15 |
| OGV | 0 | 1 | 13 | 0 | 2 | 59 |
| TheLandsharks | 0 | 0 | 2 | 0 | 0 | 14 |
| anthonyrangel | 1 | 0 | 1 | 0 | 0 | 7 |
| Markgus13 | 1 | 0 | 4 | 0 | 0 | 27 |

Richard now has 4 fully supported / 78 scoped partial / 0 wholly insufficient
records in the coverage classifier, but only 10 scalar process assessments.
The former five insufficient records preserve descriptive dimensions rather
than quality magnitudes. Partial must NOT be interpreted as gradable overall.
This is a semantic classification correction, not improved manager performance.
All Trading outcome scalars remain unavailable. Per-record confidence,
dimensions, limitations, boundaries and generation identities are retained in
the local derived panel for calibration.

## Real Waiver scoped conclusions

These compare contemporaneously priced adds/drops only; they do not grade
FAAB efficiency, roster fit or overall waiver skill.

| Manager | Higher observed Market | Lower observed Market |
| --- | ---: | ---: |
| RichardDavis47 | 4 | 3 |
| danreilley | 7 | 3 |
| davefedex | 7 | 9 |
| garrettadame36 | 1 | 2 |
| Mears30 | 1 | 0 |
| zkobes | 2 | 3 |
| OGV | 10 | 11 |
| TheLandsharks | 2 | 4 |
| anthonyrangel | 0 | 0 |
| Markgus13 | 1 | 1 |

Actual differences and later outcome changes/horizons are now retained, not
just these distribution counts. Unknown FAAB is not zero and not a penalty.
Draft timestamp-dependent process remains unavailable for the verified source
limitation. Historical roster reference precision is unchanged.

## Validation and next boundary

23 focused historical-transaction, coverage and export tests passed before
the corrected real replay. Both real replays completed for all ten managers.
No comprehensive gate or release occurred. Category aggregation still requires
scope-aware calibration; these distributions are not a completed multi-category
FOIS panel. Richard's Results-only diagnostic remains 86.52/B.

Remaining: Trading/Waiver category calibration, roster quality, second-league
quality proof, Pick range/confidence/portfolio/parity and release acceptance.
Batch 5 is not started.
