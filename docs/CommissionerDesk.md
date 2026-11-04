# Commissioner Desk

## Purpose

The Commissioner Desk is the DTOS homepage and executive briefing. It organizes the daily Front Office experience around three questions:

1. **What changed?** Verified events since the previous stored visit.
2. **What matters?** Deterministic headlines derived from current league facts.
3. **What should I do?** Prioritized, confidence-scored recommendations with inspectable evidence.

It is a foundation for future intelligence, not an AI speculation layer. Missing historical inputs are disclosed rather than inferred.

## Architecture

The feature separates responsibilities into four layers:

- `models/commissioner.py` defines immutable context and intelligence contracts.
- `services/commissioner.py` selects active context and builds briefings, headlines, snapshots, and presentation-neutral view models.
- `src/core/decision_engine/` owns shared team evaluations, window classification, and recommendations.
- `components/commissioner.py` renders reusable, responsive HTML components and owns browser-local context persistence.
- `routes/hq.py` validates query inputs, requests the view model, and renders the composed Desk.

The service consumes existing cached league data and the Team Headquarters calculation service. Page loads do not trigger additional league API calls beyond the application's existing freshness policy.

## Data models

- `ActiveLeague` identifies the selected league and season.
- `ActiveFrontOffice` identifies the selected franchise, owner, and team.
- `LeagueEvent` represents a sourced transaction or future historical event.
- `LeagueHeadline` contains a deterministic statement and its evidence.
- `DailyBriefing` contains the visit window, event list, counts, and unavailable-history disclosures.
- `Recommendation` contains priority, confidence, action, reasoning, supporting metrics, and a future explanation hook.
- `RecommendationPriority` and `ConfidenceScore` enforce consistent recommendation metadata.

The current release supplies one `ActiveLeague`, but the selector and service operate on a collection. A future league repository can replace `_league_contexts()` without changing the components or route contract.

## Component hierarchy

```text
CommissionerDesk
├── CommissionerHeader
│   ├── ActiveLeagueSelector
│   ├── ActiveFrontOfficeSelector
│   ├── Synchronization status/action
│   └── Quick navigation
├── SinceLastVisit
├── LeagueHeadlines
├── FrontOfficeSummary
├── RecommendationPanel
├── LeagueIntelligence
├── LeagueSnapshot
└── LeaguePersonality extension points
```

Each component is a standalone rendering function receiving the presentation-neutral view model. Components can be extracted or reused on future DTOS pages without moving calculation logic into templates.

## Active context and persistence

The URL is the server-rendered source of truth:

- `league=<Sleeper league id>`
- `front_office=<roster id>`
- `since=<ISO-8601 timestamp>`

The Commissioner header stores the selected values under:

- `dtos.activeLeague`
- `dtos.activeFrontOffice`
- `dtos.lastCommissionerVisit`

On a later visit, valid stored selections are restored into the URL before rendering personalized follow-up requests. Invalid or stale context values safely fall back to the first available league or Front Office.

No user account, cookie, or server-side identity is introduced in v0.9.3.

## Explainable intelligence

Every recommendation exposes:

- Priority
- Confidence score
- Explicit action
- Deterministic reasoning
- Supporting metrics
- A named future-engine hook

Current recommendations consume the shared Decision Engine and identify observable performance, roster-construction, age, depth, and draft-capital conditions. Current Championship Outlook and Future Outlook remain separate. Recommendations do not claim player value, trade availability, injury prognosis, or championship probability.

## Extension points

Future engines can populate existing contracts and stable component regions:

- Player Intelligence can enrich recommendation evidence and roster alerts.
- Trade Intelligence can supply realistic actions after values exist.
- GM Intelligence can add owner-specific preferences and decision history.
- Draft Intelligence can replace foundation pick-coverage heuristics.
- League Intelligence can add historical trends and movement.
- Predictive analytics can populate Competitive Window and trajectory fields.
- AI briefings can explain already-sourced facts through the future explanation hooks.
- Multi-league management can provide additional `ActiveLeague` instances.
- Authentication can replace browser-local default context without changing the view model.
- League branding, awards, rivalries, records, notes, and milestones can populate League Personality cards.

## Future roadmap

The next intelligence releases should add persistent historical snapshots first. Historical standings, injuries, matchup completion, and league records are required before DTOS can truthfully report movement or trends. Value and prediction engines should follow only after their inputs and validation standards are documented.

## Developer notes

- Keep Commissioner calculations deterministic and presentation-neutral.
- Add evidence to `LeagueHeadline`; never render a claim without it.
- Never create a `Recommendation` without confidence, reasoning, and supporting metrics.
- Preserve URL parameters when adding new personalized sections.
- Preserve `DTOS_CACHE_FILE` and other runtime overrides.
- Maintain Windows-compatible paths and commands.
- Add tests for context switching, missing data, invalid selections, and stable recommendation ordering.
- The responsive layout uses explicit 950px and 650px breakpoints and inherits the global dark color tokens.
