# DTOS v1.5.10 Intelligence Quality Audit

This audit evaluates whether DTOS outputs are internally consistent with
observable league data and the calibrated valuation contract. It does not encode
subjective player takes or add new intelligence.

## Root cause and corrections

League comparison teams were evaluated with intrinsic-only Asset Intelligence
while the selected Front Office used calibrated Player Value and Market
Intelligence. As a result, changing the selected Front Office could change the
entire league ranking table. The comparison path now evaluates every roster with
the same neutral Asset context and one request-scoped cached market consensus.

Team Intelligence also retained the pre-v1.5.9 draft-pick round table. It now
uses the canonical pick evaluator, preserving one source of truth.

Two presentation semantics were corrected without changing values:

- `Elite Assets` counts only Elite Franchise Players; Cornerstones remain a
  separate count.
- older low-value players are called Veteran Depth or Veteran Replacement rather
  than Developmental.

## League-wide comparison

The table reflects the production-shaped cached league after the corrections.
Grades and rankings are league-relative preseason projections.

| Rank | Team | Owner | Grade | Competitive window | Playoff | Title | Average age | Strongest | Weakest | Draft capital | Flexibility | Elite | Cornerstones |
|---:|---|---|---|---|---:|---:|---:|---|---|---|---|---:|---:|
| 1 | Mears30 | Mears30 | A+ | Elite Contender | 86% | 47% | 24.4 | QB | TE | D (#8) | A- (#3) | 0 | 4 |
| 2 | Puka cola quantum | RichardDavis47 | A | Elite Contender | 78% | 41% | 26.2 | QB | TE | F (#9) | D (#8) | 3 | 2 |
| 3 | High Rollers | anthonyrangel | A- | Contender | 70% | 35% | 25.1 | QB | TE | A- (#3) | A (#2) | 2 | 2 |
| 4 | Runaway McBride | danreilley | A- | Playoff Team | 62% | 29% | 26.9 | QB | TE | B (#6) | A- (#4) | 1 | 3 |
| 5 | Week3 is a bigger joke | garrettadame36 | B+ | Re-tooling | 46% | 20% | 24.1 | QB | RB | A+ (#1) | A+ (#1) | 0 | 1 |
| 6 | The Longest Yard | TheLandsharks | B | Playoff Team | 54% | 20% | 26.1 | RB | TE | C (#7) | C (#7) | 1 | 0 |
| 7 | zkobes | zkobes | C | Rebuilding | 38% | 11% | 27.4 | WR | TE | A- (#3) | B (#6) | 1 | 1 |
| 8 | Markgus13 | Markgus13 | D | Rebuilding | 22% | 2% | 24.3 | QB | WR | A (#2) | F (#9) | 0 | 0 |
| 9 | Mentally Unstable | davefedex | F | Rebuilding | 30% | 2% | 26.7 | QB | WR | F (#10) | F (#10) | 0 | 1 |
| 10 | Bottom Feeders | OGV | F | Full Rebuild | 14% | 1% | 26.3 | QB | WR | B+ (#5) | B+ (#5) | 0 | 1 |

## Player and roster findings

Elite anchors including Josh Allen, Ja'Marr Chase, Bijan Robinson, Puka Nacua,
Jahmyr Gibbs, Lamar Jackson, and Jaxon Smith-Njigba remain elite. Brock Bowers,
Joe Burrow, Justin Jefferson, and comparable premium assets remain Cornerstones.
Depth and replacement assets do not receive premium classifications merely from
age or roster quantity.

The audit retains independent intrinsic value, market consensus, calibrated
value, contender value, rebuild value, risk, scarcity, and uncertainty evidence.
No player-specific production exception was introduced.

## Pick and trade findings

All first- through fourth-round categories preserve round, slot, and future-year
relationships. Unknown slots remain neutral. Two ordinary thirds remain below an
elite player, and low-value aggregation cannot pass premium-package guardrails.

The audit inspected 12 prioritized dossiers for each of ten Front Offices. No
accepted dossier violated the 72% market floor or exchanged three sub-300 assets
for a 675-plus premium asset. Aggressive but economically supported offers remain
visible.

## Golden benchmark

The benchmark contains 82 permanent scenarios:

- 40 calibrated player profiles across every value tier;
- 10 draft picks across rounds, slots, and horizons;
- 12 positional archetypes across QB, RB, WR, and TE;
- 10 contender, playoff, retool, rebuild, and full-rebuild scenarios;
- 10 realistic and rejected trade-package relationships.

It validates determinism, tier boundaries, age-appropriate labels, context-stable
league comparisons, pick ordering, window classification, and trade economics.

## Known limitations

- Playoff and championship odds are deterministic preseason heuristics, not
  simulations.
- Unknown future pick slots are intentionally neutral.
- Live production, injuries, and projections remain limited to supported,
  attributable providers.
- Manager behavior models remain conservative where historical samples are low.
