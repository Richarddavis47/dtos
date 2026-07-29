# Competitive Window Contract

## Purpose

DTOS v1.5.11 replaces competing team-window classifiers with one immutable,
explainable contract. A window is a league-relative strategic classification,
not a raw player-count or record label.

## Canonical contract

`src/core/competitive_window` owns the public enum, data contract, and sole
classifier. The contract contains:

- classification;
- confidence;
- championship, playoff, and rebuild scores;
- reasons, strengths, and weaknesses;
- UTC generation timestamp;
- contract schema version.

Consumers use the enum and contract. A raw string is emitted only at a
presentation or compatibility boundary.

## Authoritative computation

Team Intelligence calculates calibrated league-relative current, overall,
future, starter, depth, youth, draft-capital, and risk inputs. It invokes
`build_competitive_window` once per roster. No other module classifies,
translates, or overrides the result.

The classification thresholds remain the audited v1.5.10 thresholds:

- Elite Contender: current at least 85 and overall at least 80;
- Contender: current at least 70 and overall at least 65;
- Playoff Team: current at least 52;
- Full Rebuild: current below 25 and future below 35;
- Rebuilding: current below 40;
- Re-tooling: all remaining combinations.

## Execution and dependency flow

```text
League data
  -> Decision horizon inputs
  -> Asset and Market valuation
  -> Player Value
  -> Roster and Team Intelligence
  -> canonical Competitive Window
  -> Decision recommendations
  -> Front Office Intelligence
  -> Trade Intelligence
  -> unified recommendation
  -> API and UI serialization
```

Initial Decision evaluation deliberately leaves the window unset. Asset and
valuation work use an explicit pending-window context, preventing a circular
dependency. After Team Intelligence creates the contracts, the orchestrator
attaches each exact object to its Decision result and passes those decisions to
all downstream consumers.

## Audit of former duplicate paths

Before v1.5.11:

- Decision Engine classified five older window labels from absolute current and
  future scores.
- Team Intelligence independently classified six calibrated league-relative
  labels.
- Front Office translated Decision labels into a third vocabulary.
- The application service replaced the Front Office label after analysis.
- Trade Intelligence ran before Team Intelligence and serialized the stale
  Decision label.

All classifier, translation, and post-hoc override paths above were removed.
The shared orchestrator cache stores the finished result containing the same
contract objects; it does not recompute classifications.

## Serialization and compatibility

The unified intelligence API and public crawl Team Intelligence payload expose
the full contract. Existing `current_window` strings remain available at legacy
presentation boundaries and are derived directly from
`contract.classification.value`.

## Extension rules

New consumers must depend on `CompetitiveWindowContract`. New diagnostic fields
may be added without changing classification semantics. Any future formula or
threshold change must update the contract version, golden scenarios, and
league-wide consistency tests together.
