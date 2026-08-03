# Automated Market Calibration Dashboard

DTOS v1.7.1 continuously audits its own valuation health without assigning values by hand. The audit runs after successful Sleeper and public-provider refreshes, traverses every canonical player and draft pick, and stores a compact report and retained history in the normal DTOS cache.

## Principles

- Consensus is evidence, not truth.
- DTOS intrinsic value remains independent and traceable.
- Calibration occurs only through category-level model parameters.
- Individual assets cannot be overridden.
- Weak, stale, contradictory, or incomplete evidence produces monitoring recommendations rather than changes.
- Every recommendation exposes evidence, confidence, affected systems, impact, and safety checks.

## Audit and categories

The audit covers rostered players, free agents, rookies, supported inactive players, and every canonical pick-ledger asset. It aggregates Quarterbacks, Running Backs, Wide Receivers, Tight Ends, elite players, veterans, rookies, future/early/late picks, young assets, and contender/rebuilder assets. Category results disclose audited and comparable counts so missing intrinsic evidence is never hidden.

## Automatic calibration safety rails

An adjustment requires a `Calibration Required` finding, at least 50 comparable assets, confidence of at least 90, two healthy market providers, current data, complete identity integrity, and a bounded adjustment. Each automatic multiplier is capped at three percent per audit. The multiplier changes only the league-adjusted valuation layer; intrinsic and provider layers remain unchanged.

Most audits are expected to apply nothing. `No calibration required` is a valid retained history outcome.

## Impact and history

Recommendations rank downstream exposure across Team Intelligence, Trade Intelligence, FOIS, championship and playoff outlooks, rankings, grades, and trade recommendations. History records the model version, evidence summary, confidence, before/after summary metrics, affected count, predicted impact, applied adjustments, and a placeholder for later observed-impact measurement.

## Interfaces

- Dashboard: `GET /valuation/calibration`
- Full report: `GET /api/valuation/calibration`
- Category health: `GET /api/valuation/calibration/categories`
- Recommendations: `GET /api/valuation/calibration/recommendations`
- History: `GET /api/valuation/calibration/history`
- DINS: `GET /api/inspect/valuation`

Provider adapters remain pluggable through the existing valuation and data-platform boundaries. Unsupported providers remain explicit and never block the audit.
