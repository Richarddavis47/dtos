# Batch 4 prepared Picks read and residual scalar sweep

## Evidence boundaries

The retained production request completed HTTP 200 in 52,058.48 ms. Its request
log does not include stage timings; those cannot be reconstructed retrospectively.
Static tracing establishes `/picks` → `build_pick_reports` → `pick_report` → full
`analyze`, including roster, front-office and trade generation per owner. This is
unnecessary work for a prepared Pick read. The corrected route never enters that
pipeline. No claim is made that every millisecond of the old request has been
attributed or that a local measurement is a new Render production measurement.

## Source-backed authenticated candidate proof

`BATCH4_PREPARED_PICK_READ_PANEL.json` records fresh public source identities and
quotes through candidate preparation, then the real account activation endpoint,
AccountContextMiddleware, LeagueContextMiddleware and corrected Picks route.
The local diagnostic uses TestClient, not a deployed production session. Its
temporary local accounts/store are deleted automatically. No private production
evidence transfer occurred. No new route was registered in production.

| Read | HTTP | Local prepared read ms |
|---|---:|---:|
| Cold-but-prepared Day Traders | 200 | 19.017 |
| Warm Day Traders | 200 | 16.086 |
| Switch to Super Flexxxin | 200 | 17.705 |
| Return to Day Traders | 200 | 19.224 |

Source fetching plus bounded Pick preparation took 1,537.593 ms outside read timing.
This is not full FOIS preparation time. No arbitrary new latency gate is imposed.
The existing Linux Market route/readiness gates retain their original contracts;
the source scan found no dedicated pre-existing Picks millisecond threshold.

Authenticated prepared fingerprints cover league/settings/playoff configuration,
all 120/90 pick identities and owners, Market inputs and selected prices, range and
confidence, and portfolio distributions. A and restored A match exactly, including
rendered page output; B differs. Day Traders has four rounds, Super Flexxxin three.
Both retain UNKNOWN/LOW ranges and generic FantasyCalc quotes. Source inventories
still have no unknown/conflicting owners. Earlier accepted production ownership,
browser identity restoration and cross-league FOIS proofs are reused, not relabeled
as this local test. Full corrected production-path acceptance remains pending release.

## Bounded residual-score sweep

Concrete remaining matches were corrected:

- Asset pick portfolio no longer combines inventory with legacy option scores or
  a hardcoded four-round/12-pick quality benchmark. Counts remain evidence; score
  is unavailable, including an empty inventory (zero inventory is not zero quality).
- Trade assets keep external acquisition price but no longer populate dynasty,
  redraft or fit scalars from calculated pick points or a neutral placeholder.
- The acquisition-package shortlist orders priced picks by acquisition price,
  explicitly not intrinsic quality. Missing prices remain excluded.
- Legacy `dynasty_pick_value` now returns unavailable utility with identity evidence.
- Decision adapters propagate missing pick utility rather than casting to a number.
- Shared assessment identity includes `pick-evidence-no-scalar-v1`, preventing
  cached pre-correction derived meaning from sharing the new generation identity.

`normalize_pick` remains a standalone compatibility utility with unit tests; the
bounded search found no active consumer call. No remaining production read of
`report.dynasty_value.score` was found. External Pick prices, range engine, canonical
portfolio distribution and FOIS methodology were not redesigned.

Focused validation: 47 tests passed. The first expanded run exposed obsolete
tests expecting fabricated current/future utility, a duplicate pick plus a
standings-only EARLY range, and an automatic repair with no supported advantage.
They now test explicit availability, unique identity, UNKNOWN range and the honest
no-repair state. Package-shape and actual Trade API tests continue to pass.

Candidate has not been released or deployed. No comprehensive gate is claimed.
Batch 5 is not started.
