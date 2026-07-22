# Data Normalization and Identity Resolution

## Mandatory boundary

Provider-specific formats must become normalized DTOS contracts before storage, consensus, APIs, or intelligence. The flow is External Provider → Registry → Normalizer → Consensus → Data Platform → Intelligence Orchestrator.

## Canonical identity

`PlayerIdentityResolver` maps Sleeper, FantasyCalc, KeepTradeCut, FantasyPros, Underdog, and Dynasty Daddy identifiers to one DTOS ID. It also reconciles normalized names, aliases, team abbreviations, position eligibility, free agents, and rookies without an NFL assignment.

Unresolved identifiers are blocked with a reason; fuzzy guessing is intentionally excluded.

## Normalized contracts

`NormalizedPlayer` contains canonical identity, football metadata, provider IDs, and aliases. `NormalizedValue` contains canonical identity, provider, value, ranks, tier, ADP, UTC timestamp, confidence, source field, and warnings.

`DataEnvelope` adds availability, reliability, and normalization metadata to source, freshness, confidence, cache, quality, and limitation fields.

## Validation

Normalization rejects nonnumeric and impossible values and reports broken identifiers. Quality checks continue detecting missing, duplicate, stale, disagreeing, and invalid records. Provider objects never cross into intelligence engines.

## Consensus 2.1

Consensus weights normalized values by provider confidence, observed reliability, freshness, outlier distance, agreement, and coverage. Missing providers reduce confidence but do not block available legitimate data. Individual provider opinions remain visible.
