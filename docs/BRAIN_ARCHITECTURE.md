# DTOS Brain Architecture

## There is only one Brain.

All future DTOS intelligence features must consume the canonical Brain rather than implement independent valuation, evidence-quality, provider-weighting, confidence, agreement, or coverage logic.

The synchronized data pipeline builds one immutable `valuation_intelligence` snapshot after provider ingestion. `BrainService` is the only public read boundary over that snapshot. It performs no network I/O and no valuation recalculation. Application services obtain it through the Intelligence Orchestrator, so Team Headquarters, FOIS, trades, recommendations, team and roster intelligence, league intelligence, Asset Intelligence, and player dossiers share one source.

## Consumer contract

`BrainService.asset()` returns the canonical asset record with its five independent valuation layers, evidence categories, provider contributions, Coverage, Confidence, Agreement, explanation, diagnostics, and history. `BrainService.decision()` adds Decision Confidence without changing asset confidence.

Decision Confidence combines evidence confidence, agreement, coverage, roster and league context, calibration safety, recommendation stability, and an explicit complexity penalty. Every component and its rationale is returned separately.

## Caching and performance

The service reads only the synchronized in-memory snapshot. Page rendering never invokes a provider or regenerates valuation intelligence. Health responses expose snapshot availability, cache mode, read latency, and request-time external-call counts.

## Migration and compatibility

The public `/api/brain` contract is canonical. Existing `/api/valuation` payloads remain supported as compatibility adapters. `/api/brain/migration` identifies migrated, legacy, and deprecated paths, while `/brain` provides the operational dashboard.

New consumers must depend on `src.core.brain`, preferably through the Intelligence Orchestrator. Direct assembly of equivalent valuation fields is deprecated.
