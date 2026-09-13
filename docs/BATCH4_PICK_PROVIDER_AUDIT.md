# Pick provider audit — 2026-09-13

Read-only public feed inspection; no production changes. Snapshot coverage,
not a permanent provider guarantee. Candidate integration remains incomplete.

| Provider | Year | Rounds | Concept | Count |
| --- | --- | --- | --- | --- |
| FantasyCalc | 2027 | 1–4 | Generic plus Early/Mid/Late | 16 |
| FantasyCalc | 2028–2029 | 1–4 | Generic only | 8 |
| DynastyProcess | 2026 | 1–5 | Exact slots 01–12 | 60 |
| DynastyProcess | 2027 | 1–5 | Generic plus Early/Mid/Late | 20 |
| DynastyProcess | 2028 | 1–5 | Generic only | 5 |

## FantasyCalc

Exact inspected endpoint:
https://api.fantasycalc.com/values/current?isDynasty=true&numQbs=2&numTeams=12&ppr=1

24 PICK rows. Format is explicitly dynasty/12 teams/2QB/PPR=1. TE-premium
semantics are not established by the response. Values remain native provider
units until compatible normalization is proven. No source-update timestamp
was supplied in these quote rows; retrieval is not provider-update time.
No exact-slot quote was observed. Synthetic FP IDs are provider identities,
not Sleeper player identities or actual league pick ownership.

The range ID suffix is zero-based (early_0 is first round); generic IDs use
one-based round numbers. The new parser verifies the ID against the source
label and rejects conflicts. No generic-to-range price conversion is permitted.

## DynastyProcess

Source: https://raw.githubusercontent.com/dynastyprocess/data/master/files/values.csv

85 PICK rows with separate 1QB/2QB native values; source scrape date September
11, 2026. Pick rows lack player crosswalk IDs. Official methodology describes
provider-modelled pick values, not observed transaction prices:
https://dynastyprocess.com/values/

The documented baseline is 12-team PPR; 2QB is derived. TE-premium compatibility
is unproven. Generic, range and exact-slot observations remain distinct.
An exact 2026 quote does not price a 2027 pick or establish a league slot.

## Admission and remaining work

Providers remain separate: equivalent scales/formats are not proven for
combined consensus. External model-derived evidence is not internal DTOS
evidence, but its methodology must be disclosed. Single-provider evidence is
allowed only at its own compatible concept, freshness and scale boundary.

Existing ingestion discarded DynastyProcess picks via player-only crosswalk;
FantasyCalc FP keys could be retained in the player-keyed map but never matched
to actual league picks. Neither constitutes integrated canonical pick pricing.

13 focused identity/Trade-price tests pass. Remaining: typed quote retention,
freshness/normalization admission, active consumer integration, league-specific
range/slot evidence and production verification. Missing prices stay unavailable.
