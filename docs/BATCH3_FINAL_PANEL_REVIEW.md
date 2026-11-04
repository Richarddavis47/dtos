# Batch 3 — 57-player checkpoint review

The bounded consumer ledger is closed. The candidate panel evaluates 398 retained
source players and selects 57 for inspection. It is not a fresh provider fetch or
production acceptance. Outputs and complete profiles are in ignored
`.validation/batch3-final-player-panel.md` and its JSON companion. Input checksums
are retained in the JSON. No rejected scalar or intrinsic rank is published.

## Evidence and outlier classification

| Case | Retained-source candidate output | Classification / interpretation |
| --- | --- | --- |
| Josh Allen | FantasyCalc raw 10431, normalized 908, provider overall rank 1; quality 72.4368; historical confidence 81; weekly 20.1 | JUSTIFIED distinct units: provider price/rank and demonstrated quality do not claim the same thing |
| Jayden Daniels | FantasyCalc raw 6556, normalized 672, provider overall rank 15; quality 63.6332; historical confidence 55; weekly 18.23 | JUSTIFIED / FORMAT MISMATCH for cross-rank comparison: no DTOS intrinsic rank is asserted and no rank was targeted |
| George Kittle | Quality 79.8799; longevity context 54.28; weekly 10.08; Market raw 2153 | JUSTIFIED separation: strong historical quality is not indefinitely repeatable future production; designation is not recovery probability |
| Jonnu Smith | Quality 57.8746; latest usage 41.1049 in 2025; depth 2; weekly 3.51; Market raw 129 | JUSTIFIED separation: prior production, latest observed role, current source context and price remain separate; no bargain claim |
| Joe Mixon | Quality 75.2409; historical confidence 51; latest usage 2024; weekly unavailable/no_projection; Market raw 67 | LOW CONFIDENCE / corrected DATA DEFECT: no fabricated 0.00 projection; team absent and Out remain disclosed facts, not invented career forecasts |
| Jordan Love | Quality 56.7871, confidence 77 with seven-season-source preparation; weekly 16.41 | DATA COVERAGE change versus early limited-history diagnostic: quality now comes from retained multi-season summaries, never from price or projection |
| Christian McCaffrey | Quality 84.2177; weekly 20.92; longevity 31.18 | JUSTIFIED: strong current/historical contribution and shorter lifecycle context can coexist; neither becomes a precise dynasty scalar |
| Rookies without NFL history | Production/usage unavailable, historical sample confidence 0; supported weekly expectations retained where present | LOW CONFIDENCE specifically for historical evidence, not zero ability; age is displayed, and unsupported profile dimensions remain unavailable |
| Bowers/Henderson/Mendoza/Tyson | Weekly evidence unavailable with source status/designation displayed independently | Missing is not zero; no replacement by price or old production |

Market evidence confidence is 54 for this retained single-provider panel because
provider publication freshness is unknown (85 input confidence × 0.90 reliability
× 0.70 unknown-freshness weight, rounded). There is no source-count penalty.
This is not a new observed confidence estimate from trading outcomes.

Provider positional ranks were not retained; the panel does not reconstruct them
from its 57 rows. Provider overall rank/tier retain their external scope.
League-adjusted rank/utility and long-term intrinsic scalar/tier remain unavailable.
FantasyCalc is the panel's explicit source; DynastyProcess is not mixed into it.

No unexplained cross-unit bargain/overpay remains in this panel. This checkpoint
does not independently verify provider judgments, certify unsupported longevity
for no-history cases, or assert production readiness. The absent dimensions and
unknown source-format defaults remain disclosed limitations, not guessed inputs.

## Planned completion work now underway

Structured Market change reasons distinguish raw price movement, normalized-index
movement, source rank/tier movement, confidence movement and methodology boundaries.
An unchanged timestamp refresh produces UNCHANGED_EVIDENCE, not movement. Price
history now records raw provider prices so normalization-population shifts cannot
masquerade as a provider changing its quote. Old differently scoped observations
remain separated. Rank movement without a price change does not claim a cause
unless additional evidence proves why the provider rank moved.

Still required: complete cross-engine trend integration and bounded storage/replay
proof, full cross-engine/real multi-league acceptance, authoritative release gates,
immutable release/deployment, controlled restart and cleanup. Batch 4 NOT STARTED.
