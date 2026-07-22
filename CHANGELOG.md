# Changelog

Notable DTOS changes are recorded here from the repository's Git history.

## v1.0.0 - 2026-07-21

- Stabilized Decision, Asset, Trade, Front Office, and Market Intelligence behind the single Intelligence Orchestrator boundary.
- Added validated production configuration with preserved environment overrides and configurable intelligence/market cache TTLs.
- Added structured JSON logging, request correlation IDs, request/error/runtime metrics, startup timing, and expanded health reporting.
- Added a single permanent release-validation entry point covering documentation, architecture, whitespace, compilation, lint, dependencies, regression tests, routes, OpenAPI, HTTP smoke tests, and process cleanup.
- Added production-readiness, large-league, cache-performance, configuration, observability, documentation, and architecture regression coverage.
- Froze and documented v1 public APIs, compatibility guarantees, and deprecation policy.
- Completed installation, architecture, developer, deployment, configuration, validation, API, market-provider, caching, release, contribution, troubleshooting, versioning, readiness, and validation-report documentation.
- Added updated architecture diagrams, production-readiness checklist, and post-release v1.1 roadmap.
- Updated application metadata to DTOS v1.0.0, build 1000, codename Front Office Operating System.

## v0.9.9 - 2026-07-21

- Added Market Intelligence as a fifth provider behind the unified Intelligence Orchestrator.
- Added replaceable FantasyCalc, KeepTradeCut, Sleeper ADP, and DynastyProcess adapters with explicit missing-provider behavior.
- Added robust market consensus, agreement, dispersion, confidence, intrinsic-versus-market value gaps, opportunity discovery, and explainable evidence.
- Added persistent-capable provider snapshot history with 7-day, 30-day, season, and career trends, momentum, volatility, and confidence drift.
- Added execution-mode-aware provider caching, explicit cached fallback, freshness and age reporting, invalidation, provider health, and offline isolation.
- Enriched player dossiers and Trade Dossiers with provider-backed market context while preserving DTOS intrinsic evaluations.
- Extended `/api/intelligence` and `/api/platform/health` with backward-compatible market output.
- Added provider, consensus, outlier, value-gap, trend, history, cache, offline, recovery, health, and cross-engine regression coverage.
- Updated application metadata to DTOS v0.9.9, build 909, codename Market Intelligence v1.

## v0.9.8 - 2026-07-21

- Added the unified Intelligence Orchestrator, shared request context, provider registry, timed pipeline, and one final recommendation contract.
- Combined Decision, Asset, Trade, and Front Office evidence with explicit conflict resolution, counterarguments, assumptions, change conditions, and centralized confidence.
- Added shared TTL caching for league decisions, asset portfolios, Front Office profiles, trade evaluations, and final results, including refresh invalidation and health metrics.
- Added `/api/intelligence` and `/api/platform/health` without changing existing API contracts.
- Updated Commissioner Desk, Team Headquarters, Trade Center, and Front Office services to reuse the same orchestration result.
- Promoted route, OpenAPI, lifecycle, process, smoke, and release validation behind `src/platform/validation/`.
- Added cross-engine, API compatibility, cache, performance, health, and validation-platform regression tests.
- Updated application metadata to DTOS v0.9.8, build 908, codename Intelligence Integration Platform v1.

## v0.9.7 - 2026-07-21

- Added centralized Front Office Intelligence profiles derived only from observable cached fantasy-football actions.
- Added deterministic competitive windows, organizational philosophies, activity profiles, negotiation styles, asset preferences, evidence, confidence, and explicit sparse-data defaults.
- Added pairwise Trade Compatibility, conservative Negotiation Forecasts, and an informational league relationship graph.
- Updated Trade Intelligence to consume shared Front Office Intelligence rather than maintaining duplicate partner logic.
- Added Front Office dossiers at `/front-offices` and a stable `/api/front-offices` contract, with Commissioner Desk navigation and Team Headquarters integration.
- Added privacy and fairness boundaries prohibiting personal-trait inference and unsupported manager judgments.
- Added focused behavioral, integration, relationship, probability-threshold, and API/page contract tests.
- Updated application metadata to DTOS v0.9.7, build 907, codename Front Office Intelligence v1.

## v0.9.6 - 2026-07-21

- Added a centralized Trade Intelligence module that consumes Decision Engine and Asset Intelligence outputs without duplicating their evaluations.
- Added deterministic partner compatibility, balanced package generation, contextual trade impacts, opportunity prioritization, and negotiation guardrails.
- Added support for 1-for-1, 2-for-1, 3-for-2, player-plus-pick, pick-package, and multi-asset proposal structures.
- Added explainable Trade Dossiers covering both sides, current and future impact, risk, evidence, alternatives, fallback, counter, and walk-away guidance.
- Added the read-only Trade Intelligence Center at `/trades` and a stable `/api/trades` contract.
- Connected Team Headquarters and shared navigation to Trade Intelligence.
- Added focused tests for package realism, evidence, engine reuse, API/page parity, and contextual evaluation.
- Updated application metadata to DTOS v0.9.6, build 906, codename Trade Intelligence v1.

## v0.9.5 - 2026-07-20

- Added a centralized Asset Intelligence module as the shared source of player and draft-pick evaluations.
- Added contextual player dossiers with independent Dynasty, Redraft, Market, and Team Fit values.
- Added traceable evidence, explicit confidence, limitations, risk, opportunity horizons, conservative archetypes, and contextual recommendations.
- Added deterministic draft-pick value, uncertainty, expected range, time horizon, and strategic recommendation reports.
- Updated player pages and the draft-pick ledger with collapsed supporting evidence while preserving the existing visual system.
- Added a canonical cached `/api/players` dossier index and optional lightweight player inclusion in `/api/league`.
- Replaced Decision Engine player and pick heuristics with Asset Intelligence portfolio adapters.
- Added focused Asset Intelligence contract tests and architecture documentation.
- Updated application metadata to DTOS v0.9.5, build 905, codename Asset Intelligence v1.

## v0.9.4 - 2026-07-20

- Added a centralized, reusable Decision Engine with typed context, profile, evaluation, team-window, and recommendation contracts.
- Separated Current Championship Outlook from Future Outlook and added independent Depth and Asset Health evaluations.
- Added deterministic positional depth analysis, five competitive-window classifications, and contextual recommendation categories.
- Standardized recommendation priority, confidence, metrics, collapsed reasoning, and future explanation hooks across DTOS.
- Connected Commissioner Desk and Team Headquarters intelligence surfaces to the shared engine without redesigning either page.
- Replaced the ambiguous overall team grade with a clearly scoped Roster Construction grade.
- Added Decision Philosophy documentation and focused engine contract tests.
- Updated application metadata to DTOS v0.9.4, build 904, codename Decision Engine v1.

## v0.9.3 - 2026-07-20

- Replaced the homepage with the Commissioner Desk executive briefing organized around what changed, what matters, and what to do.
- Added extensible Active League and Active Front Office models, selectors, URL state, and browser-local persistence.
- Added deterministic daily briefings, evidence-backed league headlines, personalized Front Office summaries, explainable prioritized recommendations, league intelligence, and expandable league snapshots.
- Added reusable Commissioner models, services, and presentation components with future intelligence hooks.
- Removed the hardcoded league identity from shared application chrome and added league-personality extension points.
- Added `docs/CommissionerDesk.md`, expanded the README, and added targeted Commissioner Desk tests.
- Updated application metadata to DTOS v0.9.3, build 903, codename Commissioner Desk.

## v0.9.2 - 2026-07-20

- Rebuilt every franchise detail page as a responsive Team Headquarters with front-office identity, assets, performance, roster rooms, draft capital, recent activity, future outlook, and quick actions.
- Added deterministic, explainable roster-construction grades for core positions, youth, depth, draft capital, flexibility, and the overall team.
- Added objective Front Office Summaries that disclose missing data and avoid speculative player-value or competitive claims.
- Added reusable Team Headquarters calculation and view-model services plus targeted unit tests.
- Added `DTOS_PHILOSOPHY.md` to establish evidence-first, transparent, deterministic standards for future intelligence systems.
- Updated application metadata to DTOS v0.9.2, build 902, codename Team Headquarters.

## v0.9.1 - 2026-07-20

- Rebuilt the Transactions page as a responsive Front Office dashboard with activity summaries.
- Added cached filtering by team, owner, transaction type, player, draft-pick involvement, date range, and search text.
- Added sortable transaction columns, configurable pagination, team links, player transaction pages, position badges, asset movement details, and preserved raw Sleeper payload access.
- Added transaction-only Sleeper synchronization with preserved filter state, last-successful-refresh reporting, and graceful failure handling.
- Added a dedicated transaction business-logic service and targeted unit tests.
- Updated application metadata to DTOS v0.9.1, build 901, codename Transactions Center.

## v0.9.0 - 2026-07-20

- Completed the Settings migration into `routes/settings.py`.
- Moved health, API, and synchronization endpoints into `routes/api.py` so `dtos_app.py` remains focused on application setup and router registration.
- Centralized application name, version, build number, and release codename in `app_metadata.py`.
- Added DTOS version, build, Git branch, and latest commit information to the Settings page.
- Cleaned and reorganized `dtos_app.py` without changing existing endpoint behavior.
- Made the default cache location portable across Linux and Windows.

## v0.8.9 - 2026-07-20

- Moved the Draft Picks page from `dtos_app.py` into a dependency-injected router in `routes/draft.py`.
- Registered the Draft router with the FastAPI application while preserving the existing `/picks` endpoint behavior.

## v0.8.8 - 2026-07-20

- Moved transaction history rendering from `dtos_app.py` into `routes/transactions.py`.
- Registered the Transactions router through the shared application dependencies.
- Refreshed the repository's packaged DTOS archive.

## v0.8.7 - 2026-07-20

- Moved the Front Office HQ dashboard from `dtos_app.py` into `routes/hq.py`.
- Registered the HQ router through the shared application dependencies.

## v0.8.6 - 2026-07-19

- Moved team list and team detail routes from `dtos_app.py` into `routes/teams.py`.
- Registered the Teams router through the shared application dependencies.
- Added a packaged v0.8.5 archive to the repository at that point in history.

## v0.8.5 - 2026-07-19

- Moved matchup list and matchup detail routes from `dtos_app.py` into `routes/matchups.py`.
- Registered the Matchups router through the shared application dependencies.
- Added a packaged DTOS archive to the repository.
