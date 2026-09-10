# Batch 3 — exact provider format audit

Status: provider relationship classified; consumer ledger remains OPEN.
Reviewed 2026-09-09. This does not certify final player outputs or authorize release.

## Exact consumed feeds

`src/core/data_platform/provider_activation.py` consumes FantasyCalc
`/values/current?isDynasty=true&numQbs=2&numTeams=12&ppr=1` and
DynastyProcess `data/master/files/values.csv`, selecting `value_2qb`.

| Dimension | FantasyCalc consumed feed | DynastyProcess consumed feed |
|---|---|---|
| League size | Explicit request: 12 | Public methodology describes 12; current CSV has no per-row confirmation |
| QB format | Request `numQbs=2`; provider describes its alternate model as Superflex | `value_2qb`; public methodology describes 2QB/Superflex conversion |
| Reception scoring | Explicit request: PPR 1 | Public methodology describes PPR; no current per-row format marker |
| TE premium | Parameter absent; default not proven | Not explicitly documented for current file; unknown |
| Player units | Provider trade-value units, not points or intrinsic quality | Rank-derived provider value units, not points or intrinsic quality |
| Scale limits | DTOS config uses 0–12000; not a proven provider hard maximum | DTOS config uses 0–10000; public formula starts with factor 10500, not a certified bound |
| Picks | Current adapter admits only rows with Sleeper player IDs; no pick quote integration | Combined source contains picks; DTOS admits only mapped player rows, not pick rows |
| Player universe | Returned mapped players, not guaranteed exhaustive rookies/veterans | ECR-ranked mapped players; missing/ambiguous crosswalks excluded, not zero-valued |
| Source time | Adapter retains retrieval time; source publication time unavailable | `scrape_date` retained separately from retrieval time; day precision |
| Format customization | Supported provider settings are not roster/team fit | No DTOS speculative format transformation permitted |

## Authoritative evidence and its limits

[FantasyCalc FAQ](https://fantasycalc.com/frequently-asked-questions) describes
optimization on real trades, outlier removal, separate 1QB/Superflex models and
regression adjustments for PPR, league size and TE premium. Recency-weighted
implied trade values determine price. The documented model is exponential rather
than linear. It also describes a roughly 300-player replacement context and
calculator waiver adjustments. These statements do not establish the default
TE-premium setting of an API request that omits it, an absolute numeric ceiling,
an update SLA, or exact equivalence to another provider's scale. DTOS does not
apply the calculator's package waiver adjustment as a player quote.

[DynastyProcess methodology](https://dynastyprocess.com/values/) is dated June
2020. It describes FantasyPros dynasty ECR, exponential valuation
`10500 * exp(ECR * -0.0235)`, 12-team PPR, an approximately 300-player rostered
universe, and a historical LOESS conversion to 2QB/Superflex. It describes modeled
rookie picks separately. These are documented historical assumptions, not proof
that the present implementation is unchanged.

The [current public values workflow](https://github.com/dynastyprocess/data/blob/master/.github/workflows/weekly-playervalues.yml)
schedules Friday builds at 02:23 UTC and invokes `build_pickecr.R`,
`build_playerecr.R`, and `build_values.R` from the **private** `dynastyprocess/db`
repository. The actual current transformation cannot be inspected through that
public workflow. A schedule is not proof of successful publication or freshness.
No access to that private repository was attempted.

## Decision

**INCOMPATIBLE / UNKNOWN for a shared normalized consensus.**

Both sources provide legitimate external evidence, with different underlying
methodologies. Their apparent broad 12-team/PPR/2QB alignment does not resolve
the missing material assumptions. The existing DTOS numeric normalization is a
local representation, not a validated cross-provider economic transformation.
No speculative QB/TE-premium conversion is introduced.

Until a shared contract is proven, show separate provider evidence. If just one
usable source participates, identify SINGLE-PROVIDER MARKET and retain its
evidence confidence without a count-only penalty. If incompatible sources are
present and no explicit source is selected, the generic combined result is
MARKET UNAVAILABLE, not an arbitrary average or arbitrary preferred provider.
Quotes remain inspectable. Missing consensus does not mean missing raw evidence.

## Six-part ledger entry

- Source semantic: external source-specific dynasty market evidence.
- Unit: provider raw units; DTOS normalized units remain provider-specific.
- Scope: exact requested/source format; not league utility or roster fit.
- Generation: source observation plus normalization methodology; retrieval is not publication.
- Availability: quote availability and combined-consensus eligibility are distinct.
- Consumer meaning: source-specific price reference, never intrinsic value.

Implemented focused boundary proof: canonical consensus, provider-network output,
Market API serialization and evidence presentation retain separate quotes and
explicit evidence states. Brain no longer reconstructs agreement from incompatible
raw observations after consensus declines them. Calibration diagnostics no longer
equate healthy-feed count with independent compatible evidence.

Focused validation: 19 consensus/API/evidence tests, two active provider-network
tests, and three Brain agreement/missing-evidence tests passed. These are focused
proofs, not the comprehensive release gates or the final player panel.

Remaining: finish evidence-state/source selection through all active
API/view models; complete the final consumer sweep; verify provider-specific
normalization bounds; final 57-player panel. No ledger closure claimed.
