# DTOS Development Roadmap

DTOS is the Day Traders Front Office System: a live dynasty-fantasy-football command center built on Sleeper data and expanded with league-specific analytics, history, owner intelligence, and decision support.

## Product principle

Every screen should answer its primary fantasy-football question in under 10 seconds.

## Release workflow

Each module follows the same process:

1. Plan the complete module.
2. Build related features as one safe release.
3. Deploy through GitHub and Render.
4. Test on mobile and desktop.
5. Fix defects and polish usability.
6. Freeze the module except for bugs or high-value improvements.

---

## Current status

### Foundation — Complete

- GitHub repository and version history
- GitHub Codespaces workflow
- Render deployment pipeline
- FastAPI application
- Sleeper API synchronization
- Automatic refresh and manual Sync button
- Mobile-responsive visual system
- JSON API foundation

### Commissioner Desk — DTOS v0.9.3 foundation

- Active League and Active Front Office context
- Persistent personalized executive briefing
- Since Last Visit event foundation
- Evidence-backed league headlines
- Explainable prioritized recommendations
- League intelligence, snapshots, health, and personality extension points
- Central integration surface for future Player, Trade, GM, Draft, and predictive intelligence

### Team Headquarters — DTOS v0.9.2 foundation

Released through DTOS v0.6.0.

- League-wide franchise cards
- Individual franchise pages
- Live rosters and lineup-slot order
- Sleeper-style starting lineup
- Bench, IR, and taxi organization
- Position counts and roster summaries
- Complete future-pick ledger
- Original and current pick ownership
- Collapsible draft-capital years
- Traded-away pick tracking
- Team Report layout
- Position-room strength bars
- Front Office Analytics framework

- Front Office identity, asset snapshot, performance, roster rooms, draft capital, timeline, and quick actions
- Deterministic Front Office Summary with explicit data limitations
- Explainable foundation grades for positions, youth, depth, draft capital, flexibility, and overall roster construction
- Stable integration cards for Competitive Window, Contender, Rebuild, Player Intelligence, League History, Trade Center, and future recommendation engines

Future Team Headquarters upgrades will replace or extend calculation layers with real DTOS valuation and competitive-window models without another major page redesign.

---

### Decision Engine - DTOS v0.9.4 foundation

- Shared contextual team evaluation contracts
- Independent Current Championship and Future Outlook horizons
- Position-level depth and injury-exposure analysis
- Deterministic Asset Health and competitive-window classification
- Explainable recommendation categories, priority, confidence, evidence, and extension hooks
- Reusable integration surface for Commissioner Desk, Team HQ, Trade Center, Player Intelligence, GM Intelligence, League Reports, Draft Assistant, and notifications

Future releases can replace individual scoring providers without changing the Decision Engine's public output contracts or presentation components.

### Asset Intelligence - DTOS v0.9.5 foundation

- Shared contextual player and draft-pick report contracts
- Independent Dynasty, Redraft, Market, and Team Fit values
- Observable evidence, confidence, limitations, risk, and opportunity horizons
- Contextual recommendations based on league and Active Front Office inputs
- Draft-pick value, uncertainty, expected range, time horizon, and strategy
- Decision Engine integration through portfolio adapters
- Stable provider interfaces for future production, usage, contract, injury-history, and market feeds

Future releases can enrich individual evidence providers without changing dossier, Decision Engine, or presentation contracts.

### Trade Intelligence - DTOS v0.9.6 foundation

- Decision Engine and Asset Intelligence orchestration without duplicated valuation logic
- Deterministic partner compatibility and complementary-needs analysis
- Balanced single-player, consolidation, player-plus-pick, pick-package, and multi-asset generation
- Independent current/future impact and explainable roster, depth, value, risk, opportunity-cost, and market signals
- Prioritized Trade Dossiers with bilateral reasoning and negotiation guardrails
- Read-only Trade Center and API contracts for future Commissioner Desk, Team HQ, GM Intelligence, mobile, and notification integrations

Future GM and Market Intelligence providers can enrich acceptance and negotiation context without changing proposal or dossier contracts.

### Front Office Intelligence - DTOS v0.9.7 foundation

- Evidence-backed profiles for every organization using observable fantasy-football actions only
- Competitive windows, organizational philosophies, negotiation styles, activity levels, and asset preferences
- Pairwise compatibility, conservative negotiation forecasts, and informational league relationship edges
- Shared Decision Engine and Asset Intelligence inputs with Trade Intelligence consumption
- Stable dossier, API, Commissioner Desk, and Team Headquarters integration surfaces
- Neutral defaults and unavailable probability states when historical evidence is insufficient

Future historical providers can add draft behavior, offer/counter events, and seasonal normalization without changing the public organization or compatibility contracts.

### Intelligence Integration Platform - DTOS v0.9.8 foundation

- One orchestrator and shared context across the four intelligence pillars
- Registry-based providers and a timed recommendation pipeline
- Unified evidence, conflict resolution, confidence, assumptions, counterarguments, and change conditions
- TTL caching, invalidation, cached fallback, health, and performance telemetry
- Backward-compatible unified recommendation and platform-health APIs
- First-class validation platform and cross-engine regression coverage

Future providers plug into the registry and evidence lifecycle instead of adding another application-level recommendation path.

---

## In progress

### Matchups Command Center — DTOS v0.7.0

Primary question: **Who has the advantage this week, and why?**

Planned release scope:

- Current-week matchup cards
- Team names, records, scores, and projections
- Live-versus-final matchup states
- Clickable matchup detail pages
- Side-by-side starting lineups
- Player scores and projected points when available
- Position-by-position matchup comparison
- Current leader and projected winner indicators
- Remaining-player summaries
- Matchup margin and upset-alert framework
- Mobile-first layout matching the Teams design system
- Graceful offseason and missing-projection handling

Initial analytics will be clearly labeled as framework metrics until the DTOS player-value and projection engines are complete.

---

## Next up

### Player Database

Primary question: **What is this player worth, and what should I know now?**

- League and NFL player search
- Player profile pages
- Position, team, age, experience, and status
- Current roster ownership
- Weekly and season statistics
- Market-value framework
- Trend and injury framework
- League transaction history

### Trade Center

Primary question: **What realistic trade improves my team?**

- Trade builder and analyzer
- Team-to-team asset browser
- Pick and player valuation engine
- Fairness and roster-fit scoring
- Contender and rebuild impact
- Owner-tendency integration
- Trade finder and realistic offer generation
- Historical league trade comparisons

### Draft Center

Primary question: **Who owns every pick, and what is the league-wide draft-capital picture?**

- Complete pick matrix by season and round
- Original and current ownership
- Team draft-capital rankings
- Pick-value framework
- Trade history for each pick
- Rookie-draft results and historical classes

### Transactions Center — DTOS v0.9.1 foundation

Primary question: **What changed in the league, and why does it matter?**

- Delivered current-week trades, waivers, free-agent moves, adds, and drops
- Delivered filters by team, owner, player, transaction type, picks, date, and search
- Delivered sortable and paginated asset-movement summaries
- Delivered transaction-only refresh with cached-data fallback
- Next: historical season aggregation and impact-analysis framework

### League History

Primary question: **What has happened in Day Traders since the beginning?**

- Champions and playoff results
- Standings by season
- Draft history
- Trade history
- Records and milestones
- Rivalries and head-to-head history
- Owner and franchise timelines

---

## Front Office intelligence

### Team valuation engine

- Player market values
- Draft-pick values
- Position-room grades
- Team value and roster rank
- Contender score
- Dynasty score
- Youth and liquidity scores
- Competitive-window assessment

### Owner profiles

- Confirmed owner identities
- Negotiation and response tendencies
- Risk tolerance
- Trade activity
- Preferred asset types
- Fairness and aggressiveness profiles
- Historical performance and achievements

### GM Intelligence

- Personalized recommendations
- Buy, sell, and hold guidance
- Team-specific trade targets
- Opponent and market context
- Multi-year roster planning
- News-triggered recommendations
- Natural-language front-office assistant

---

## Long-term platform goals

- Multiple-league support
- Authentication and private league access
- Persistent database instead of cache-only storage
- Scheduled historical snapshots
- Notifications and major-news alerts
- League constitution and handbook integration
- Commissioner tools
- Exportable reports
- Public and private franchise profiles
- Subscription-ready deployment architecture

---

## Version map

- **v0.1.0** — Live deployment and Sleeper synchronization
- **v0.2.0** — Teams and franchise-page foundation
- **v0.5.0** — Expanded team summaries, position grouping, and draft ownership
- **v0.6.0** — Sleeper-style starting lineups, collapsible draft capital, and Team Report
- **v0.7.0** — Matchups Command Center
- **v0.8.0** — Player Database foundation
- **v0.9.0** — Trade Center foundation
- **v0.9.1** — Transactions Center foundation
- **v0.9.2** — Team Headquarters foundation
- **v0.9.3** — Commissioner Desk foundation
- **v1.0.0** — Complete core Day Traders front-office platform
