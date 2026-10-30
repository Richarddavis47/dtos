# v1.22 / build 2215 — Trade strategy state and discovery clarity

Separate temporary Trade strategy from the saved franchise goal. Trade choices stay in the existing workspace; reload and contextual Back restore them, while fresh primary Trade entry starts from the franchise goal. Changing Trade strategy never saves or clears a goal.

My Team now labels unsaved goal previews and requires an explicit **Save goal** action to persist the goal across sessions. The existing account database holds only a bounded, account/league/franchise-scoped preference with transactional revision and authorization checks. Legacy browser-session goals remain readable and unchanged; no automatic import or restoration is performed. Existing rankings and production goals are not edited by acceptance testing.

Replace joined discovery labels with: “DTOS explored a limited set of possible offers, not every theoretical trade.” Preserve zero-result explanations, Shop leads, bilateral admission and all build 2214 discovery mathematics. No new analytical work, provider calls or analytical storage.

Technical SemVer/tag: v1.22.0; customer-facing product version: v1.22. See docs/audits/TRADE_STRATEGY_STATE_2215.md for root causes, boundaries and validation requirements.

# v1.21.114 / build 2214 — Rebuild trade discovery

Recommended Trades now covers more supported production-for-capital opportunities. Rebuild searches several exact pick maturities/rounds, retains the intended outgoing player before bounded package pruning and gives mixed returns room within the existing candidate budget. Buyer utility and own lineup costs precede a late age tie-break; age never sets a price or forces a sale.

Zero-result searches explain the main assessed limit and may identify an already-supported player to review in Shop Asset. These leads are explicitly not qualified offers. Counterparty-limited and rejected alternatives retain the existing final verdict hierarchy.

No changes to recommendation thresholds, Neutral/Custom valuations, exact picks, projections, legal lineups, historical grades, saved preferences, navigation or public/account behavior. No new provider calls, permanent storage, background work or infrastructure. Full-evaluation budget remains 180; existing phase, pool and package caps remain unchanged.

See docs/audits/REBUILD_DISCOVERY_2214.md for source tracing, live-versus-fixture evidence, preservation controls and limits. Release is conditional on the complete canonical, Product, security and resource validation against the final source tree.

# v1.21.113 / build 2213 — Custom Trade readiness and compatible Market recovery

Keep Custom Rankings and Trade readiness aligned after Market verifies that new prepared inputs reproduce its existing complete semantic generation. Admit that one verified input marker without rebinding original build provenance, changing prices or reconstructing the personal rank-slot curve. Pending, failed, superseded and genuinely different evidence still requires its existing qualification or a new publication.

Add an explicit Reload Custom evidence action for saved rankings whose prepared Trade context is unavailable. Use the existing same-page reload/workspace restoration; keep the exact offer and Neutral mode, and never silently reset rankings, switch modes, discover offers or evaluate a trade. Distinguish missing preparation from asset-price review.

Preserve saved revisions, ranks, tiers, flags, exact picks, Neutral pricing, legal lineups, recommendation thresholds, historical grades, public/account behavior and contextual Back. No new provider calls, analytical storage, polling, valuation rules or infrastructure. See docs/audits/CUSTOM_TRADE_READINESS_2213.md.

# v1.21.112 / build 2212 — Customer clarity and accessible Back

Keep the existing contextual Back link available after its header scrolls away, using a compact top strip and a reserved header slot. Preserve its DOM/tab order, focus, existing history and authorization checks, five-tab navigation and Trade workspace/fresh-entry behavior. The top strip blocks clicks on obscured content. No scroll-triggered requests or additional navigation history.

Explain projection-source timing in plain English, separate completed historical seasons from pending evidence, and show concise mode-aware Custom warnings with their full original limitations still available through disclosure. Label supported multiweek Trade lineup changes as totals rather than per-week averages. Preserve existing number formatting, unrounded comparisons, canonical facts, prices, projections, legal lineups, strategy/verdicts, grades and saved preferences.

Welcome/account behavior and build2211 Market recovery remain intact. No new provider work, analytical storage, cache or infrastructure. See docs/audits/CUSTOMER_CLARITY_2212.md for the bounded audit and acceptance contract.

# v1.21.111 / build 2211 — Market preparation and recovery

Show readable, truthful Market preparation stages from existing resident cache state. Fix dark-on-dark preparing-page copy and provide accessible recovery, qualified last-successful Market notices and bounded automatic transition to a compatible nonempty publication. Checks run only while the page is visible, at most twelve times over one minute, and never acquire a runtime, prepare a Market or call providers.

Preserve account/session/league/franchise scope and contextual Back history when opening the ready Market. Stop on failed or incompatible preparation, scope changes and repeated connection failures; keep an explicit retry and useful Home/My Team navigation. Custom asset limitations remain separate from overall Market readiness.

Pricing, source admission, subset preservation, failed-refresh evidence, Custom rank slots, Trade verdicts, projections, legal lineups, saved preferences, Welcome and account behavior remain unchanged. No new analytical storage, worker, provider polling or paid service. See docs/audits/MARKET_PREPARATION_2211.md for state contracts and limitations.

# v1.21.110 / build 2210 — Contextual Back and workspace return

Add a consistent authenticated Back control that returns through meaningful, same-tab page context rather than a fixed section landing. Preserve Market queries, explicit My Team sections, safe direct-link fallbacks and browser Back/Forward. Validate account/session/league/franchise scope before contextual or cached-page return; private context checks require no league runtime or analytics.

Restore the existing exact Trade draft, Neutral/Custom mode, strategy, temporary filters and preview/Keep/Adopt/Adjust context. Retained results remain not revalidated and pending departures are cancelled. Deliberate primary Trade-tab entry preserves the existing fresh-session policy. Keep My DTOS editor view without writing rankings. Bound temporary navigation state to 32 entries, 64 KiB and two hours; no permanent history database or recommendation cache.

Preserve Welcome/account admission, five primary destinations, prices, projections, legal lineups, Trade verdicts, exact picks, historical qualifications, saved preferences and resource safeguards. See docs/audits/CONTEXTUAL_BACK_2210.md for source audit, security boundaries and acceptance limitations.

# v1.21.109 / build 2209 — Trade workflow and discoverability

Separate Generate Trades from Evaluate Trade. Put the goal and Neutral/Custom valuation controls ahead of owned assets, keep search preferences optional, and place generated results directly beneath the primary action. Preserve exact packages and the established Preview/Keep/Adopt/Adjust lifecycle.

Use honest preparation, searching, complete, error and cancellation states; prevent duplicate submissions and reject stale or incomplete responses. An optional picks toggle maps only this search to existing exact-asset exclusions, without changing an entered offer, saved intent, selection mathematics or recommendation policy. No new persistent preference memory or automatic discovery is added.

Keep final bilateral recommendation headings authoritative. Separate qualified recommendations from optional, exploratory, rejected and unsupported alternatives; no personal upside upgrades a limited offer. Valuation, projections, legal lineups, exact picks, history, security and build 2208 lineup safeguards remain unchanged.

# v1.21.108 / build 2208 — Prepared lineup review and game-lock integrity

Keep the actual Sleeper submitted lineup separate from the prepared optimal lineup, including explicitly empty slots. Show a higher-projected lineup alert only when the exact current-week changes have compatible projections, fresh roster/preparation checks, verified player identity, eligible slots and future recorded game times. Unknown or started-game changes remain informational; no lineup is submitted automatically. Open tabs expire the actionable suggestion without polling.

Resolve optimal player names and positions, explain prepared bye/Out/unassigned-team evidence, and apply the existing projection provenance check to matchup rows and optimal disclosures. Reuse the existing bounded schedule preparation and add no ordinary-read provider, solver, FOIS, history or discovery work. Neutral/Custom valuations, Trade verdicts, historical grades and saved state remain unchanged.

The live 0/10 versus 3/10 needs count is not resolved without a matching publication identity and reconnected browser. Controlled fixtures do not establish live Day Traders or physical Safari acceptance. See docs/audits/LINEUP_REVIEW_2208.md.

# v1.21.107 / build 2207 — Projection coverage and legal eligibility

Preserve Sleeper's explicit fantasy positions separately from primary NFL position, and apply exact league slots without counting one athlete twice. Current Out/IR and already-prepared known-bye exclusions now agree across Team Strength, roster diagnostics and useful reserve production. Original quotes and genuine zero remain intact; explicit source identity conflicts are withheld.

My Team explains supported versus total lineup population and excluded starting slots. League needs distinguishes full replacement-evidence coverage from a valid starting lineup. Weekly views explain ADP-only, absent, incompatible and participation evidence without inventing projections. No new request-time source, optimizer, FOIS, discovery, history or persistence work is introduced.

Fresh authorized Sleeper source replay still supports seven of ten Day Traders lineups; all seven totals are unchanged. One dual-eligible player's usable slot is recovered, but three teams still lack complete lineups. The five reported players have ADP-only Week 8 records, not scoring projections. The original 182.03 production snapshot and live authenticated browser remain unverified; current source replay gives 185.4278. See docs/audits/PROJECTION_COVERAGE_2207.md.

# v1.21.106 / build 2206 — Trade recommendation integrity and context

Make the existing bilateral qualification the primary Trade conclusion. User-side or Custom upside remains visible as subordinate context and cannot promote a counterparty-limited, incomplete or non-executable offer. Apply the same contract to the shared explanation, preview and alternative cards; retain prior assessments as not revalidated.

Keep prepared legal-lineup comparisons distinct from stricter roster-availability diagnostics. Preserve supported numeric comparisons with conditional availability where required, name current season/week and separate multi-week totals and supported-week averages. Do not combine different windows or erase known numbers with a generic unavailable heading. Missing/incompatible comparisons remain missing, genuine zero remains zero.

No evaluation thresholds, prices, ranking preferences, projections, solver mathematics, pick identities, history/FOIS grades or discovery policy change. No extra provider, solver, FOIS, history or discovery calls are introduced by formatting. The connected live browser requires app reauthentication; reproduction and positive authenticated acceptance use disposable source-compatible fixtures, not live Day Traders evidence. See docs/audits/TRADE_RECOMMENDATION_CLARITY_2206.md for precise scope and remaining limits.

Apply the same completed-evidence admission to headline, expanded weekly totals, averages, horizon subtotals and preview/alternative explanations. Verify pinned season, week, scoring, source generation and before/after snapshot references without calculating new projections. An invalid future week does not erase independently supported current or playoff comparisons. Preserve unsupported values as missing. Correct the incomplete Preview/Keep/Adopt and precision fixtures without promoting unqualified offers or inventing numerical evidence.

# v1.21.105 / build 2205 — Historical decision evidence continuity

Join Trade player identities to existing canonical retained Market observations and the compatible neutral current endpoint. Preserve original package keys, current-price provenance, historical cutoffs, source formats and Custom/Neutral separation. Exact draft picks are not guessed into global player trends.

Keep uniquely acquired transaction periods when an active-window duplicate omits them, including genuine week zero. Conflicting periods remain unqualified; exact assets, status, ownership and source payloads are unchanged.

Keep failed, pending, cancelled and unknown-status actions explicitly qualified in My Team recent activity rather than presenting completed additions or drops. Keep those activity rows readable on narrow phones. Carry supported dated neutral movement into the existing Trade evidence disclosure. This context does not change recommendation thresholds, lineup calculations or manager-confidence rules. No new provider requests, historical imports, grades, permanent warehouse or personalized price cache.

Continue the 24-surface inventory in docs/audits/DATA_COMPLETENESS_2205.md and data_completeness_2205.csv. Source-pinned before/after controls and disposable source → cache → private HTTP → Chromium controls cover the recovered paths. Live tenant inspection remains unauthorized with the configured credential; fixture acceptance does not establish live historical completeness or production capacity.

# v1.21.104 / build 2204 — Exact partial Custom values

Preserve every saved rank slot when Market evidence is missing. Expose a supported asset’s personal value only when its existing slot is identical under every compatible completion of missing prices; otherwise withhold it. Missing assets never receive prices, and no order, tier, flag or revision is rewritten on reads. The existing full-cohort valuation rule and neutral Market mathematics are unchanged.

Allow supported Custom packages through the existing Trade workflows while dependent packages remain qualified or blocked. Explain partial availability and asset-specific recovery. Keep source/revision/publication and membership fencing, resource limits, Welcome and account behavior unchanged. See docs/audits/DATA_COMPLETENESS_2204.md for the proof, scope and unresolved production source access.

# v1.21.103 / build 2203 — Source to screen continuity

Preserve coherent full-population Market normalization references when cached preparation receives only a retained league subset. Reject changed, incomplete or mixed partial references atomically instead of deriving a new price curve from the subset. Fresh complete provider publications retain the existing normalization methodology. Saved ranking intent and Neutral/Custom separation are unchanged.

Make 320px matchup player rows readable by stacking paired sides with franchise labels. Keep wider comparisons, scores, projections, navigation and disclosures unchanged. See docs/audits/DATA_COMPLETENESS_2203.md for source qualifications and remaining gaps; private production Market access was unavailable, so this release does not claim restored numerical Custom availability for the four reported IDs.

# v1.21.102 / build 2202 — Source actuals and data completeness

Recover same-row Sleeper player actuals when starter entries are missing; preserve missing versus zero across sync and matchup presentation. Clarify projection recovery states and remove customer-facing beta labels without changing account access or demo qualifications. Preserve Custom slot-curve safeguards and saved preferences. See docs/audits/DATA_COMPLETENESS_2202.md for measured scope and unresolved inventory.

# v1.21.101 / build 2201 — Names-only welcome demonstrations

- Replace visible fictional player labels with verified NFL player names and positions.
- Retain text-only position indicators, fictional team scenarios, exact example picks and all illustrative calculations.
- State beside every demo that values and rosters are illustrative, not live player valuations or actual trades; include a visible non-endorsement statement.
- No portraits, external imagery, provider data imports, private account changes or additional anonymous analytical work.
- Make the simulated HTTP-worker test timestamp deterministic and add a predating-artifact rejection control; production watchdog and freshness checks remain unchanged.

# v1.21.100 / build 2200 — Operator diagnostics, selected league identity and Trade pickers

Trade roster pickers group actual positions QB/RB/WR/TE then other supported positions, sort prepared neutral prices descending with unavailable last, and separate exact draft picks. Selected packages, valuation policy and discovery behavior remain unchanged.

Replace raw orchestration error serialization with a stable failure category and warning while preserving protected diagnostic state and authorization. Render source-independent account headers from selected membership instead of the default league runtime, reject incompatible runtime identity, and fence asynchronous rankings reads to the rendered league/franchise/session. Preserve rankings, numerical engines and the fictional welcome page.

# DTOS v1.21.99 / build 2199 — Public Welcome and Read Only Demo

Complete the existing welcome-page candidate on secured build 2198. Anonymous `/` opens the public `/welcome` experience; authenticated Home, account creation/sign-in/recovery and protected application routes keep their existing boundaries.

Three connected, explicitly fictional and read-only demonstrations explain team strength/replacement cover/exact capital, both sides of a hypothetical trade and Neutral versus personal Custom values. Existing canonical services revalidate the frozen numerical examples offline. Public requests only serve prepared HTML, with no scripts, provider calls, solver work, Trade discovery, FOIS, history, ranking persistence or new background jobs.

All security corrections from builds 2196–2198 are preserved. The existing `orchestration.last_error` operator-health observation remains strictly behind its inspection credential, separate from the public demo and future operator hardening. No new administrative mechanism, data warehouse, production user-data change or historical-grade regeneration.

Controlled-beta status does not imply an invitation gate. Existing Create Account remains publicly reachable; this release does not authorize increased beta admission, public promotion, pricing or billing.

---

# DTOS v1.21.98 / build 2198 — Safe Cached Synchronization

Security-only correction of cached synchronization error disclosure. Successful inspection responses retain authorized last-valid facts while using stable warnings instead of raw exceptions. The shared page banner, explicit manual-sync JSON, transaction recovery and prepared health summaries follow the same rule, including legacy raw cached errors.

League/transaction failures retain safe availability-aware status. Existing cache writes no longer persist raw synchronization errors; loading an old cache qualifies its status in memory without rewriting it on read. Existing rollback, source publication, timestamps and data admission remain unchanged. Bounded server diagnostics preserve operation, exception type, correlation and at most six source locations, without exception messages, chained payloads, credentials or private source identifiers.

No new provider, solver, discovery, FOIS or history work, permanent storage, security credentials, user-data mutations, valuation changes or historical-grade regeneration. The welcome candidate remains isolated and unreleased. Independent Scout acceptance follows release.

---

# DTOS v1.21.97 / build 2197 — Private Runtime Failures

Security-only follow-up to build 2196. Handled league acquisition and explicit hydration failures retain HTTP 422/503 semantics, with fixed public error codes and recovery messages. Raw exception strings, mismatched source identifiers and paths no longer form these response bodies. HTML recovery remains available and the existing generic diagnostic 500 is unchanged.

Server-side diagnostics record correlation ID, exception type and at most six source-function locations; they never serialize exception messages, chained messages, locals or credentials. Member runtime health qualifies cached error text. Existing credential-authorized operational evidence remains protected and available. Denial and failure responses are private/no-store.

No new credentials, account/session policy, intelligence calculations, provider work, persistent analytical storage, user-data changes or historical FOIS regeneration. The public welcome candidate remains isolated pending separate independent acceptance and authorization.

---

## DTOS v1.21.96 / build 2196 — Private Diagnostic Boundaries

Security-only correction from v1.21.95. Legacy inspection now requires an active authorized league; member-specific diagnostic requests are fenced to the controlled franchise. Existing read-only operator inspection uses its existing credential and scope, without new credentials or policy changes to operational inspection.

Public health/readiness/status expose explicit deployment identity and readiness only. Raw errors, league facts and detailed operational state are no longer returned publicly. Authorized detailed health remains available to the existing inspection credential; ordinary sessions cannot read global cached operational state. Health status codes and Render probe URLs are preserved.

No public welcome page, registration/admission change, intelligence calculations, saved rankings, historical grades, production user-data mutation or new storage. The welcome candidate remains held for separate independent acceptance and later reconciliation.

---

## v1.21.95 / build 2195 — Premium Decision Hierarchy

Compact the shared account/league header and keep secondary league tools in an accessible disclosure. Bring prepared Home guidance and Market search forward, distinguish selected modes from primary actions, and present existing player evidence in one identity-led summary with quieter supporting sections. Keep Roster, Depth and Capital visible in a compact row, with secondary Trade shortcuts in the existing assessment disclosure.

Presentation only: neutral and personal values, exact assets and picks, projections, legal lineups, recommendation eligibility, saved rankings and historical qualifications are preserved. No new provider, discovery, solver, FOIS or historical preparation work, persistent records or infrastructure. Unsupported Custom assets retain deliberate recovery; no production preferences are changed. Author Chromium fixtures do not establish physical Safari or unfamiliar-user acceptance.

## v1.21.94 / build 2194 — Priced inactive dynasty assets

Keep a saved inactive player in Custom Rankings when the same compatible current Market publication supplies its exact identity and supported price. Sleeper inactivity is not retirement or absence of a dynasty price. Explain that a priced inactive asset is not confirmation of availability to play. Preserve the same saved-cohort slot curve, ordering, tiers, preferences and revision on reads.

Retired, missing, unpriced, conflicted and unsupported exact-pick assets remain qualified blockers; missing values never become zero. Individual confirmed recovery and optional Restart remain unchanged. No production ranking edits, new provider or analytical work, grading changes, storage or resource-limit changes. Authenticated production-account recovery and independent Scout acceptance remain separate from disposable author controls.

## v1.21.93 / build 2193 — Custom Rankings Compatibility & Recovery

Saved Custom Rankings now identify the exact assets whose current evidence cannot support personal values. Review cause-specific pricing, retirement, identity or exact-pick ownership limitations and retry prepared evidence without changing saved intent. A confirmed, revision-checked removal from Custom ordering preserves all other relative ranks, other tier breaks and Target/Avoid/Protect choices; Restart remains a separate full reset. Removing an asset changes the saved cohort and can change the remaining personal value slots.

Neutral Market prices, Custom slot-curve mathematics, canonical projections, legal lineups and Trade safeguards are preserved. New assets do not silently enter saved rankings; missing evidence never becomes zero. No new storage schema, providers, background analysis or historical FOIS regeneration. Author fixtures and hosted gates are separate from future Scout acceptance; exact production revision-9 asset diagnosis requires authorized account access and is not inferred from counts.

## v1.21.92 / build 2192 — Final Plain-English Experience Correction

Explain player dossier outlook, strengths, weaknesses and schedule/bye limits in football terms using the same prepared reports. Preserve genuinely supported findings and distinguish missing evidence from unfavorable evidence. Keep useful methodology and provenance in advanced disclosures rather than exposing internal scalar, baseline, threshold or evidence-object instructions in ordinary dossier content.

Explain Home strategy choices and the best projected starting lineup without inferring an unsupported competitive direction. Share identical Depth evidence limits once across the affected positions while retaining distinct positional warnings. Show supported league names and understandable Market totals in Builder, with exact source identifiers in technical evidence.

Presentation-only integration: no price, projection, lineup, verdict, eligibility, strategy, Custom valuation, saved-ranking or historical-evidence changes. No added providers, discovery, solver, FOIS, reconstruction, storage or background jobs. Production rankings and preferences are not edited or reset. Retained FOIS grades remain RETAINED / NOT REVALIDATED. Physical Safari, unfamiliar-human and independent Scout acceptance are separate from author-run Chromium fixtures. Existing beta/concurrency restrictions remain.

## v1.21.91 / build 2191 — Plain-English Decision Experience

Explain missing depth evidence as uncertainty, separately from a supported replacement weakness. Keep projected lineup rankings distinct from record/PF standing and provisional evidence visibly qualified. Preserve detailed source/availability evidence in existing disclosures.

Explain why a supported current-week trade effect can coexist with an incomplete overall recommendation. Show the other roster’s prepared benefit and cost without elevating historical manager observations or changing eligibility. Use cost/uncertainty labels rather than manufacturing a tradeoff from reassurance. Keep missing-price conditional exploration and all canonical verdicts intact.

My DTOS explains Create rankings to personalize and the Custom Trade setup prerequisite; remove repeated introductory wording while preserving saved order, Restart, recovery and Neutral/Custom behavior. Market describes comparable dated observations without internal Step 2 terminology. Home uses supported original-team labels for owned firsts and keeps exact source identifiers in Supporting evidence.

Presentation-only prepared reads: no additional provider, discovery, solver, FOIS, reconstruction, inference or durable analytical work. No pricing, projection, lineup, strategy, authorization, source-publication or cache-budget changes. Retained historical grades remain RETAINED / NOT REVALIDATED. Responsive Chromium and simulated walkthroughs are author evidence; physical Safari, unfamiliar-human and independent Scout acceptance remain open. Existing beta/concurrency restrictions remain.

## v1.21.90 / build 2190 — Custom Rankings Availability and Recovery

Use the canonical Market cache's immutable prepared-input identity for Custom Rankings compatibility. The normal provider publication has no top-level generation timestamp; requiring one rejected a ready Market directory indefinitely. Preserve explicit legacy source checks, exact league/player/pick identities, current prepared-generation admission and saved rank-slot valuation semantics. Reject input changes during directory reads and source replacement before preference commits/publication; never reset saved intent on reads or refresh.

Offer a visible Retry rankings action with Check Market and Neutral Trade recovery. Explain unavailable Custom mode in the existing Trade valuation panel. Preserve previously loaded rows for reference while disabling edits until a current read succeeds; ignore older responses after a newer read. Empty or incompatible evidence remains unavailable, not zero. Retry is a bounded prepared read, not an instruction to start discovery or providers.

Actual canonical Market → authenticated store/HTTP → rendered Chromium controls cover recovery, source races, saved edits, exact picks and Custom/Neutral Trade navigation. No provider/solver/FOIS/history/discovery factory is added to ranking reads or edits; no schema, cache-budget or persistent price-store change. Physical Safari, unfamiliar-human and independent Scout acceptance remain separate. Beta expansion remains unauthorized.

## v1.21.89 / build 2189 — Current-Manager Evidence and Waiver Activity Integrity

Bind prepared manager observations to the actual producer's league, franchise, current owner, method and unchanged source publication. Revalidate at Trade consumption and protected response publication; superseded evaluations fail with the established retryable canonical-evidence error. Prior-owner decisions remain franchise history and retained grades remain RETAINED / NOT REVALIDATED. Missing manager history is neutral; current bilateral roster and capital quality precede historical confidence tie-breaks.

Deduplicate canonical source-league/transaction identities and separate completed claims, additions and drops from failed, pending, cancelled and unknown attempts. Preserve exact asset identity, directed FAAB including zero and historical owner attribution. Apply the shared admission to League DNA, activity APIs, rendered summaries and completed Commissioner news. Explain the counterparty's current benefit and cost before qualified manager observations, sample period and limitations.

No new provider, solver, FOIS, reconstruction, discovery or persistent analytical work is introduced by these qualification reads. Market prices, Sleeper projections, legal lineups, Custom/Neutral valuation contracts, bounded caches and heavyweight execution protections remain unchanged. Responsive Chromium controls are author evidence; physical Safari, unfamiliar-human acceptance and independent Scout review remain separate. Beta expansion is not authorized.

## v1.21.88 / build 2188 — Custom Rankings Accessibility and Phone UX

Keep keyboard focus on an enabled control for the same exact asset after ranking moves, including first/last and page boundaries. Preserve visible focus, overall-position announcements and the moved asset's viewport anchor.

Browse compact ranking rows with Market/Personal values and on-demand reorder, Target/Avoid/Protect, tier and supporting controls. Put pagination above and below the list; keep search, positions and Neutral/Custom switching near the top. Preserve visible evidence warnings and scoped preferences.

Personal order/value methodology, Market prices, projections, legal lineups, Trade conclusions, persistence and security are unchanged. No provider, solver, FOIS, history reconstruction or automatic discovery is added to ordinary editing. Responsive Chromium and emulated touch remain separate from physical iPhone/Safari and independent Scout acceptance.

## v1.21.87 / build 2187 — My DTOS Custom Rankings

Add complete Market-seeded overall player and exact-pick rankings under Account, with positional search, paginated editing, drag/touch and keyboard move controls, optional tier breaks and saved Target/Avoid/Protect intent. Neutral view preserves the saved custom order; explicit confirmed Restart uses the latest compatible Market baseline while retaining separate preferences by default.

Custom DTOS assigns the current compatible Market price slots of the saved cohort to its saved global order. This personal current-value permutation never changes neutral prices, projections, legal lineup effects or opponent valuation evidence. New or unavailable identities do not acquire invented personal prices. Preserve canonical severe-loss and missing-evidence safeguards and expose separate personal and neutral conclusions across Calculator, Trade For, Shop, Recommended, Balance and Adjust.

Persist only bounded account/league/franchise-owned identity/order/tier intent in the existing account database, with private reads, CSRF, commit-time ownership/session checks, revision conflicts and stale-result publication fences. No copied price warehouse, automatic discovery, FOIS regeneration, historical reconstruction or paid infrastructure is added. Physical Safari, unfamiliar-human usability and independent Scout acceptance remain separate requirements. Beta expansion is not authorized.

## v1.21.86 / build 2186 — Phone-first Front Office Brief

Bring Home's first supported insight forward by compacting franchise identity, official record and primary actions. Place secondary franchise/context controls after the Brief. Remove redundant introductory copy and display prepared insights before secondary Find/Explore controls; loading, empty and recovery messages remain ahead of those controls. Reasons, drawbacks, exact trade assets, eligibility and all evidence disclosures are unchanged.

Preserve explicit discovery, prepared-only reads, source/strategy guards and the existing 24-entry/2 MiB/15-minute opportunity cache. No provider, solver, FOIS, historical reconstruction, background job or persistent state is added. Responsive Chromium evidence is separate from physical Safari, unfamiliar-user and independent Scout acceptance, which remain open. Existing resource and source-integrity safeguards remain unchanged.

## v1.21.85 / build 2185 — Prepared Front Office Brief

Combine Home Attention and hypothetical Trade Opportunities into one prepared Front Office Brief before completed League Trade News. Show up to four supported insights, two initially visible, each with a reason, tradeoff and existing action. Explicit manager goals determine family precedence without changing objective lineup calculations or neutral Market prices. Exact owned capital, legal replacement quality and evaluator-supported offers remain separately qualified; related needs and offers are composed using their existing pre/post diagnostics.

Read matching TeamAssessment and roster-diagnostic publications without cache-miss factories. Missing trade evidence cannot hide unrelated prepared roster/capital facts. Only eligible, fully priced favorable cached offers appear as recommendations; optional, rejected, exploratory, incomplete and stale offers are not promoted. Preserve exact opaque opportunity tokens, You Send/Receive identities and Preview/Keep Original/Adopt navigation. Source/goal changes and failed prepared reads clear obsolete client content.

No automatic discovery, provider acquisition, historical Market reader, solver, FOIS or AI work is added. Keep the existing 24-entry/2 MiB/15-minute opportunity cache, historical execution/publication protections, 2 GiB budget and 500 ms liveness requirement. No new persistence or background work. Author-run browser and comprehension walkthroughs are not physical Safari, human-usability or independent Scout acceptance. Beta expansion remains restricted.

## v1.21.84 / build 2184 — Actionable My Team outlook

Move the existing roster takeaway directly below franchise identity, record and strategy. Reuse the prepared, generation-bound TeamAssessment, positional replacement diagnostics and exact future-capital inventory to explain current position, supported strength, principal concern, future flexibility and one goal-specific action. Statistical record/PF standing remains distinct from the selected week's league-scored optimal-lineup comparison and its supported population. Missing or provisional depth is not proven weak depth; age context is descriptive, with no new sustainability forecast or overall team grade.

Keep roster, depth and capital shortcuts and read-only opponent views. Changing a goal updates the explanatory action immediately using prepared choices and the existing scoped session contract; neutral Market values, Sleeper projections and legal-lineup mathematics are unchanged. Supporting evidence is available in an accessible disclosure. No additional provider requests, FOIS/history work, solver runs, background jobs, persistent records or cache-budget changes are introduced by the formatter.

Separately display unavailable preseason directory forecasts without `None%`, preserving genuine zero, and format derived projected depth changes with the established point formatter without altering underlying precision. Phone and expert comprehension controls are author-run evidence; physical iPhone/Safari, unfamiliar-human comprehension and independent Scout acceptance are not claimed. Beta expansion remains restricted.

Keep browser test coverage, dependency packages and deadlines unchanged while selecting the official Ubuntu CI mirror after repeated measured Azure package-transfer timeouts. This changes validation setup only, not production infrastructure.

## v1.21.83 / build 2183 — FOIS flight source ownership

Release the persistent FOIS child's canonical current-source reference when its work unit completes or fails. Keep that source available throughout historical evaluation, and use the existing identity-checked release so cleanup cannot remove a newer publication or another league. Shared player identity/conflict evidence and bounded verified historical caches remain reusable. No scoring, source, schema, cache-budget or infrastructure change; retained historical grades are not regenerated or revalidated.

Disposable before/after real-engine controls preserve complete qualified score contents (excluding only observation generation time), while completed work no longer accumulates current league dictionaries in the child. This is a demonstrated worker-retention correction, not an explanation or resolution of the much larger production parent footprint, recurring memory-limit events, historical OOM or cold-Home gap. Independent Scout acceptance and production headroom observation remain required before beta expansion.

## v1.21.82 / build 2182 — Bounded historical cache residency

Share one canonical cache owner across history services, intelligence-memory exports and Weekly Reports. Bound its retained-season sections independently of runtime eviction: at most 36 compact sections and an estimated 8 MiB of Python objects, with 12 verified checksum entries. Least-recently-used sections lose cache ownership; existing readers retain their exact objects. Oversized sections remain complete on demand without permanent residency.

Serialize cold local archive decodes, recheck warm entries after admission, and invalidate superseded file identities. Source writes retain their own exact file identity; a late writer cannot attach old facts to a newer publication. Shutdown clears residency with a refill epoch fence. Cache misses verify existing local archives without fetching providers or writing historical records. Historical grades, source admission, heavyweight response bounds and the 2 GiB/500 ms contracts remain unchanged.

Independent Scout acceptance is required. This scoped residency correction does not establish the cause or resolution of the historical production OOM, the original cold-Home delay or sustained large-scale capacity.

## v1.21.81 / build 2181 — Sleeper source publication integrity

Sleeper background synchronization now installs replacement source data, including failure rollback, under the same per-runtime boundary that qualifies and publishes complete historical responses. Heavy source work remains outside that boundary. Source transitions mark existing FOIS evidence pending and advance its publication revision; restoring an old source pointer cannot silently make an in-flight historical response current again.

Configured-default, selected-league and cold-recovery sync paths share this protocol. Repeated cancellation drains the writing thread before ownership is released. Complete history, source identities, historical grading, request bounds and the 2 GiB/500 ms contracts remain unchanged. Deterministic controls use the real Sleeper sync thread and both historical HTTP APIs. Independent Scout acceptance is required; this release does not establish production OOM resolution, cold-Home attribution or sustained multi-league capacity.

The transaction-only refresh also commits its bounded source mutation through the same runtime boundary, preserving shared consumer references. A fetch based on an older source cannot overwrite or modify a newer source after a concurrent full synchronization.

## v1.21.80 / build 2180 — Historical publication integrity

- Pin the admitted league context, source generations and FOIS publication revision for full-history profile and timeline responses. Recheck qualification immediately before committing successful response headers; superseded verified evidence is RETAINED / NOT REVALIDATED, and lost or incompatible league contexts fail safely with retryable unavailability.
- Serialize qualification changes and header handoff through a per-runtime publication boundary. Keep heavyweight reconstruction, bulk serialization and backpressured output outside that boundary and inside the existing single-response resource lease.
- Finalize only a bounded metadata prefix in the parent. Preserve complete verified historical bodies, source checksums, exact identities, retained grades, the eight-root / 8 MiB memo and cleanup on cancellation or error. No grading, schema, persistent cache or infrastructure change.
- Deterministic controls cover same-context A→B refreshes, child reconstruction/serialization, publication interleavings and cleanup. Production OOM, the original cold-Home delay and sustained multi-league capacity remain unresolved; independent Scout acceptance is required.

## v1.21.79 / build 2179 — Bounded historical requests

- Admit one complete FOIS profile/timeline API response across all accounts and leagues, with no queued heavy results. Coordinate admission with existing heavy phases and cgroup headroom; return qualified retryable unavailability when resources are busy.
- Verify retained evidence and serialize complete JSON in one disposable, read-only child. Produce the response row by row into an anonymous temporary file, preserving exact evidence, canonical JSON, current/retained qualifications and the eight-root / 8 MiB memo. No permanent response archive or schema change.
- Hold ownership through backpressured response output and cleanup. Bound preparation and output time, retire children on cancellation or parent death, and drain cleanup before allowing another request. Ordinary liveness remains on the serving event loop.
- Controlled Python 3.14.3 / 2 GiB external probes verify complete 193/384/1,153-row responses, overlap rejection, source-file stability and cancellation. These are author-run fixtures, not a production OOM resolution or a sustained scalability guarantee. Historical grades remain RETAINED / NOT REVALIDATED; independent Scout acceptance is required.

## v1.21.78 / build 2178 — Historical delta integrity

- Reject non-string object paths, non-integer or boolean array indices, invalid bounds and incompatible path/container combinations before admitting retained historical evidence. Do not normalize malformed paths into apparently valid evidence.
- Stage only shallow copies of changed ancestor containers. Invalid later instructions leave the private base and operation values unchanged; valid reads keep the summary optimization and avoid full-tree copies. The eight-root / 8 MiB per-read memo, hash/byte/scope/dependency checks and independent returned evidence remain intact.
- Qualify invalid retained history with HTTP 503 across GM profile, full profile and timeline consumers; do not expose a misleading historical assessment. No grade regeneration, valuation change, schema, persistent cache or infrastructure change. Production OOM, profile latency and sustained multi-league scalability remain unresolved; independent Scout acceptance is required.

## v1.21.76 / build 2176 — Chronological history and bounded FOIS reads

## v1.21.77 / build 2177 — Verified retained-history efficiency

- Apply retained deltas only to privately owned decoded trees, preserving every hash, byte-count, scope and dependency check while avoiding redundant deep copies and JSON reparsing.
- Keep verified lightweight history summaries for HTML profiles. Full DTO validation still runs for every retained row; full-evidence APIs, provenance, grades and RETAINED / NOT REVALIDATED qualification are unchanged.
- Preserve the per-read eight-root/8 MiB serialized memo, source generations, storage schemas and infrastructure. Disposable Python 3.14.3 / 2 GiB controls compare identical evidence, allocations, multi-league and concurrent publication behavior.
- Historical production OOM, original cold Home gap and unmeasured production waiting remain open. Fixture improvements are not a universal production latency or capacity guarantee; independent Scout acceptance remains required.


- Select historical Market observations by validated quote instants and source-knowledge cutoffs, preserving fractional precision, UTC-offset equivalence, exact identity and genuine zero. Stream candidates without unsafe text-ordered truncation; equal times use immutable observation IDs without rewriting retained evidence.
- Reuse only identical, fully verified FOIS semantic roots within one timeline call, bounded to eight roots / 8 MiB of existing serialized bytes. Keep recursive validation, independently owned results, ordinary concurrent publication and all retained-grade qualifications. No grading, source, schema or persistent-cache change.
- Split bounded profile diagnostics into retained SQL fetch, decode, current-score classification and rankings. Disposable profiling is author-run evidence, not proof that historical production OOM, cold delay, worker contention or sustained liveness is resolved. Independent Scout acceptance remains required.

## v1.21.75 / build 2175 — Qualified preparation and FOIS profile diagnostics

- Use the same selected league/NFL season-week evidence for projection horizons and Team Strength. Preserve the original Sleeper calendar fields and reject incompatible league, scoring, week or generation inputs; pin one projection publication through preparation.
- Capture scheduled checkpoints at their actual timezone-aware observation time, keeping milestone labels in event identity. Reject unsupported timestamps individually and compare quote/knowledge cutoffs as typed UTC instants, including fractional seconds. Preserve genuine zero prices and existing retained records.
- Extend bounded, payload-free profile tracing across context, retained lookup, history, activity/behavior, qualification and rendering. Add Team Strength/checkpoint/profile memory boundaries to the existing sampler without additional computation, archives, schemas, infrastructure or cache limits.
- Preserve Home/FOIS failure isolation, cancellation cleanup, canonical intelligence, authorization and RETAINED / NOT REVALIDATED historical grades. Original production OOM, cold-delay attribution and sustained 2 GiB safety remain unproven; independent Scout acceptance is required.

## v1.21.74 / build 2174 — Request-correlated reliability diagnostics

- Distinguish request/account/runtime admission, transport headers, HTTPX hook work, full body transfer, JSON parsing, projection/valuation preparation, cache publication and Home/body completion with bounded, payload-free correlated clocks.
- Observe parent/FOIS-child processes, qualified PSS/RSS and cgroup anonymous/file memory around existing heavy work. Use capped sampling and the existing hosted log sink; no new diagnostic endpoint, database, source archive, resource allowance or infrastructure.
- Keep browser-driver heap budgeting and Python-version setup fixtures in validation only. Preserve all test coverage and the unchanged 2 GiB/500 ms gates, canonical sources, authorization, runtime ownership and FOIS cancellation/retained-grade boundaries.
- These are diagnostic boundaries, not a claimed latency or production OOM fix. Original incident causes remain open unless new correlated evidence establishes them. Author-run evidence requires independent Scout review.

## v1.21.73 / build 2173 — Navigation ownership and bounded sync diagnostics

- Keep a league runtime owned from cold admission through the complete response. Restore the existing warm-cache bound after overlapping reads; preserve active writers and shared hydration through repeated cancellation.
- Emit one bounded numeric sync profile for source, processing and publication phases, including qualified process/cgroup samples. Provide an isolated authenticated 2 GiB residency reproduction without new permanent storage, source calls, projection/Market changes or FOIS revalidation.
- Production OOM causation and the original 50-second cold-source delay remain open until measured in production. No universal cold-start or 2 GiB safety claim; independent Scout acceptance is required.

## v1.21.72 / build 2172 — FOIS navigation isolation and owned-worker cleanup

- Publish supported league context before optional FOIS preparation. Home/account/league browsing stays available during slow or failed FOIS work, with league-scoped pending/unavailable or retained/not-revalidated evidence; explicit computation reports pending or a qualified failure.
- Use existing runtime-owned maintenance and one bounded compute slot. Remove duplicate hydration generations, serialize admission against an already-running Market build, and drain submission, shutdown and publication through repeated cancellation before scratch cleanup. Timed-out or broken workers are reaped before returning.
- Preserve canonical sources, projections, legal lineups, reserve-quality and recommendation safeguards, account isolation and retained historical grades. No new schema, permanent archive, worker service, cache limit or infrastructure. Production OOM causation remains unresolved; bounded measurements do not establish complete production safety. Independent Scout verification is required.

## v1.21.71 / build 2171 — Useful reserve production in trade decisions

- Trade evaluation now distinguishes useful projected replacement strength from available reserve slots. A same-count 40→1 loss appears as a real depth cost rather than “No material downside.”
- Meaningful starter upgrades and supported strategic premiums remain possible with disclosed depth costs. Shop and Adjust reuse the same qualified reserve evidence; complete prior/current trade evidence remains accessible through existing disclosures.
- No new valuation or projection model, roster score, permanent archive, schema or infrastructure. Canonical sources, security, historical provenance and retained FOIS grades are preserved. Author-run acceptance is separate from independent Scout review and physical-device testing.

## v1.21.70 / build 2170 — Qualified historical Market comparisons

- Wire the current selected canonical Market observation into the existing historical trend evaluator. Compatible 100/120/200 evidence now reports +100; history-only comparisons remain explicit when current evidence is missing or incompatible.
- Preserve asset, units, method, dates and source generations; exclude future/unsupported observations and contradictory generations. Report comparison scope/dates and v2 method metadata consistently, with a canonical history link from player dossiers.
- Reuse existing prepared evidence and bounded caches without provider calls, new schema, archives, snapshots or FOIS regeneration. Preserve Market arithmetic, Trade recommendation policy, Sleeper projections and legal-lineup formulas. Independent Scout acceptance remains required.

## v1.21.69 / build 2169 — Historical provenance and missing-data presentation

- Retained historical facts carry the checksum of the same verified source snapshot, including during concurrent publication replacement. No second mutable generation read or invented checksum is used.
- Historical player pages explain unavailable scoring without raw None metrics; supported zero remains numeric and unsupported individual metrics stay qualified.
- Preserve v1.21.68 admission, birth-date conflicts, exact identities, historical pricing/reconstruction safeguards and canonical Trade/Market/Sleeper behavior. No new schema, archive, provider requests, paid infrastructure or retained FOIS regeneration. Independent Scout acceptance remains required.

## v1.21.68 / build 2168 — Historical evidence admission and identity integrity

- Close retained-source bypasses for unverified future weeks and missing/incompatible league scoring. Career totals, leaderboards and historical production consume qualified facts through the same boundary; supported completed Day Traders/Arkham evidence and genuine zero remain usable.
- Keep accepted birth-date conflicts intact when a provider identity update is rejected. Later single-date refreshes and cache reload cannot restore unjustified age certainty. Historical ages continue to use the decision date.
- Requalify existing compact checkpoints without rewriting source files. No new storage, schema, paid infrastructure, Market/Trade/projection policy change or retained FOIS regeneration. Grades remain RETAINED / NOT REVALIDATED; the integration batch stays open until Scout independently accepts the release.

## v1.21.67 / build 2167 — Historical player-week and age integration

- Project existing prepared Sleeper completed-week observations into canonical historical player/week and matchup records. Preserve league-specific scores, explicit starter roles, source identity, missing-versus-zero semantics and bounded read behavior. Future placeholders remain excluded; decision-time consumers retain their stricter completed-week cutoff.
- Preserve supported birth dates through normalization, canonical updates, ordinary existing-cache publication/reload and compact process handoff. Compute age at the decision date, qualify missing/invalid/conflicting or mismatched identities, and never substitute current age.
- Carry prepared observations through the existing isolated-worker handoff and qualify incomplete season-to-date coverage. Reuse historical player, franchise-state and transaction consumers without a warehouse, schema, additional provider requests or new valuation/lineup model. Retained FOIS grades remain RETAINED / NOT REVALIDATED; no production regeneration or historical migration.
- Captured read-only Day Traders/Arkham Week 5 fixtures reproduce 285/273 supported player entries. Author-run source/HTTP, real-spawn and responsive Chromium controls are separate from Scout's independent acceptance and physical iPhone/Safari or human testing. Preserve the 2 GiB and 500 ms release gates.

## v1.21.66 / build 2166 — Historical evidence integrity

- Admit historical franchise-state prices only with supported canonical Market units, source/comparison identity, normalization/method and decision-eligible clocks. Withhold mixed currencies and unsupported totals/window labels; preserve compatible observations and genuine zero. Older-than-seven-day quotes remain numeric, qualified evidence.
- Separate transaction-period acquisition, dated roster anchors and event-order coverage. Missing periods/records or uncertain anchors qualify reconstructed ownership, cap confidence and withhold unsupported competitive windows and process grades. Preserve observed trades, exact picks and owner identities.
- Apply the shared price boundary to preparation-time FOIS decision context and propagate reconstruction limitations. Retained historical FOIS grades remain RETAINED / NOT REVALIDATED; no regeneration, source rewrite, schema, archive or paid infrastructure. Market/Trade/Sleeper/lineup rules and 2 GiB/500 ms gates are unchanged.

## v1.21.65 / build 2165 — Missing-price decision clarity

- Keep the canonical assessment vocabulary while placing a separate conditional-exploration / not-an-endorsement qualification beside a favorable but ineligible missing-price assessment.
- State that Market cost cannot be fully assessed; preserve known lineup gains, strategy, reserve costs and source qualifications in primary and disclosed evidence. Keep missing-price discovery guards and eligibility unchanged.
- Align server, fallback, offer, Balance/Preview and older bounded saved-field presentation. Add actual source/HTTP and responsive-browser controls without new storage, dependencies, calculation changes or recommendation recalibration. Scout-independent and physical-device/human acceptance remain separate.

## v1.21.64 / build 2164 — Recommendation integrity

- Apply the existing severe-Market-loss safeguard to player-only evaluations; a trivial positive lineup change cannot rescue a 995-to-75 return. Require existing material weekly production evidence before positive-horizon endorsement.
- Preserve meaningful intentional overpays, complementary bilateral exchanges, strategy-specific capital policy, exact canonical Market/Sleeper evidence and legal lineup calculations. Keep legality, user-side judgment, counterparty plausibility and generated eligibility separate.
- Add actual publisher/evaluator/authenticated HTTP and released-client regression controls across strategies, Trade For, Shop, Recommended and Adjust. No new storage, source writes, FOIS regeneration or unrelated UI/history changes. Independent Scout and physical-device/human acceptance remain separate.

## v1.21.63 / build 2163 — Cancellation cleanup

- Keep every cancellation-drain wait shielded while the existing scratch-preparation thread is active. Repeated cancellation cannot make cleanup race that thread or recreate an orphan directory; propagate cancellation after completion and never submit/publish abandoned work.
- Preserve normal preparation failures and successful computation/publication. Add deterministic real-storage controls for repeated cancellation, preparation failure, thirty mixed operations without temporary growth, graceful POSIX interruption and the documented hard-kill limitation.
- Extend the existing Linux recovery/lifecycle gate with these controls. No new persistent store, schema, janitor, source archive, paid infrastructure, calculation or account/Trade changes; unchanged 2 GiB / 500 ms gates. SIGKILL/power loss cannot execute application cleanup and may leave scratch; no unsafe sweeping of active copies is introduced.
- Independent Scout review, physical iPhone/Safari, screen-reader and unfamiliar-user acceptance remain separate. Author-operated automated evidence does not establish unconditional public readiness.

## v1.21.62 / build 2162 — Franchise import recovery

- Give manual and discovered unmatched-franchise imports the same clearly labeled Your leagues and Review Sleeper identity recovery actions, using existing authenticated destinations.
- Explain that no ownership was guessed and saved leagues/selection remain unchanged. Preserve authorization, CSRF, atomic import commits and source-supported successful retries.
- Add actual account-store/HTTP and authenticated native-browser coverage for both submitted forms, recovery navigation, discovery failure, session expiration, CSRF rejection, safe retry and phone/keyboard controls. No schema, saved state, cache, source or intelligence changes; unchanged 2 GiB/500 ms gates. Scout-independent, physical iPhone/Safari and unfamiliar-user acceptance remain separate.

## v1.21.61 / build 2161 — League source recovery

- Stop cold selected-league preparation before intelligence work when Sleeper sync has no retained supported facts. Return a bounded unavailable response instead of an empty-input500; retain valid existing facts and ordinary retry behavior.
- Keep account recovery, lightweight health/readiness and static assets independent of league hydration while preserving existing authentication, CSRF, preparation, revision and activation checks.
- Give browser source failures same-origin retry and account/league recovery actions. Preserve structured API failures. Show existing saved connections with explicit not-refreshed qualification when discovery is unavailable; do not fabricate current source facts or write account records.
- Drain an in-flight FOIS scratch-database preparation thread before cancellation removes its temporary directory. Preserve cancellation, published evidence and the unchanged graceful-shutdown/resource gates; add deterministic barrier regression coverage to lifecycle CI.
- Preserve all Trade, Market, exact Sleeper projection, legal-lineup, prior-assessment, historical and FOIS contracts. No new persistent store/schema/cache or infrastructure. Unchanged2GiB/500ms gates; physical Safari and unfamiliar-human acceptance remain separate.

## v1.21.60 / build 2160 — Atomic imports and truthful lineup evidence

- Commit prepared league imports atomically: recheck the existing account revision, account/Sleeper identity and live session, then save membership, series/season references and active selection in the same existing SQLite transaction. A stale operation returns conflict without account-state changes. Provider preparation remains outside the write lock.
- Preserve source-supported imports and retries; roll back all account rows on a failed commit. Keep existing authentication/CSRF, no-membership guidance, loading feedback and activation protections; expose Your leagues from the conflict page for a deliberate retry.
- Label Commissioner’s existing metric Optimal Projected Lineup. Show supported projected points, scoring league/week, comparison population, lineup-relative grade and evidence coverage/limitations. Keep Competitive Window separate; remove borrowed card-confidence percentages and format percentile ordinals correctly.
- Reuse existing source/assessment evidence and SQL writers. No schema, tables, import-attempt history, duplicate sources or new permanent cache. Preserve Market, Sleeper projections, legal-lineup math, recommendations, Trade, historical/FOIS contracts and unchanged 500 ms / 2 GiB gates.

## v1.21.59 / build 2159 — First-use recovery and evidence

- Keep Sleeper connection and league-add failures actionable without guessing ownership or changing the active league. Finish league preparation before saving a new membership; preserve existing authentication and source admission.
- Show connection/import progress, restore controls on browser history navigation, expose existing account recovery and keep readable form fields inside their phone cards.
- Give browser Market warming a concise retry/Home/My Team page while preserving the existing API/JSON, background preparation and bounded cache contracts. No automatic polling or fabricated prices.
- Disclose already-retained counterparty package explanations and absolute before/after lineup totals as previous, NOT REVALIDATED evidence. No recalculation, additional stored fields or assessment copies.
- Preserve all Trade, Market, projection, legal-lineup, historical and FOIS contracts; no new permanent store or schema. Unchanged 500 ms liveness and 2 GiB resource gates. Responsive Chromium is separate from physical iPhone/Safari and Scout-independent acceptance.

## v1.21.58 / build 2158 — Complete retained evidence and canonical Market display

- Expose complete already-saved prior assessment evidence inside the closed Previous assessment / NOT REVALIDATED disclosure. Preserve original counterparty, qualified lineup costs, risks, all supported limitations, strategy and source context; keep current incomplete results separate.
- Reuse canonical adjustment display strings in Balance and Preview Compare. Match the existing decimal half-even display contract in editable Market/Calculator labels and the evaluated Trade Market panel without changing arithmetic, projections, prices, generations or target intent.
- Preserve bounded existing draft/prior state and all Preview/Keep/Adopt, reevaluation, reset, navigation, exact-protection and isolation contracts. No new persistence, schema, archive, snapshot or provider work; unchanged 500 ms / 2 GiB gates.
- Correct validation-only graceful shutdown ordering so the application drains its workers before process-group escalation; retain the existing 15-second bound. Scope the legacy rendered test to the current result while preserving all prior assertions.
- Reap abandoned optional FOIS scratch computations on cancellation/shutdown instead of waiting for a running process-pool job after its caller is gone. Preserve published evidence, normal calculations and recovery; retain existing resource and liveness gates.

## v1.21.57 / build 2157 — Trade assessment and phone integrity

- Keep selected player names, positions/teams, exact picks and controls readable on narrow phones; place supporting Market/protection disclosures below the full-width identity.
- Put complete Balance packages and coherent current Market totals before concise supported reasoning and the main drawback. Keep full evaluator/counterparty evidence on demand; format derived totals without changing arithmetic or canonical Sleeper displays.
- Separate current complete/incomplete evaluation attempts from genuine retained assessments. Preserve one prior assessment, clearly not revalidated, when a new attempt is incomplete; successful compatible reevaluation restores current status. Preserve failure/reset/newer-intent safety.
- Preserve target-first Balance, exact protections, Preview/Keep Original/explicit Adopt, Home draft boundaries, canonical pricing/projections, legal lineups, source qualifications and retained FOIS grades. No new permanent store or model; unchanged 500 ms / 2 GiB gates.

## v1.21.56 / build 2156 — Canonical projection display parity

- Reuse the prepared canonical player/week projection display in Trade facts, matching the player dossier without a second screen-specific rounding policy.
- Preserve raw Sleeper projections, legal-lineup calculations, recommendation labels, Market values and every v1.21.55 Trade workflow. Genuine zeros and unavailable evidence keep their supported source display.
- Add actual-publisher/evaluator and authenticated route/Chromium controls for fractional and zero projections. This is a forward correction to immutable v1.21.55; no new model, store or infrastructure.

## v1.21.55 / build 2155 — Trade decision experience

- Lead Trade evaluation with a concise roster-specific decision, current Market totals/bar, starter versus depth impact, main cost and material qualification. Keep complete evaluator, weekly, positional and source evidence available on demand.
- Name unresolved competitive direction precisely for future-capital trades. Offer explicit WIN NOW / RETOOL / REBUILD selection and separate conditional considerations without changing recommendation standards, canonical prices or legal lineups.
- Bring selected-player Sleeper projections and prepared actual production into Trade with scoring, season/week, sample, freshness and source generation. Label Market ranks accurately; do not invent season or points-per-game ranks.
- Put Shop target, scope, search action/status and results before manual asset inventory. Clarify automatic versus explicit search and preserve honest empty/error recovery without completion scroll jumps.
- Prioritize target-preserving Balance options; separate any changed-target ideas and show complete packages/totals. Preview, Keep Original and explicit Adopt remain required.
- Apply the revised navigation contract: Home ends this tab's proposal; internal steps, supporting returns and active reload preserve work. Keep strategy independent, separate cloned opener-tab drafts, and prevent history/late-response resurrection.
- Use shared phone standings headers and aligned statistics without changing order, cutoff or badge meanings. Preserve readable names, source limitations, exact protections and retained FOIS grades.
- No new permanent store, provider loop, valuation/projection model or historical regeneration. Unchanged 500 ms liveness and 2 GiB gates. Contract: [Trade decision experience](docs/TRADE_DECISION_EXPERIENCE.md).

## v1.21.54 / build 2154 — Historical evidence integrity

- Qualify truncated or invalid retained gzip seasons without breaking League or own/opponent Team HQ. Continue valid independent evidence, preserve corrupt originals and recover after an explicit valid publication.
- Separate completed decisions from supported, partial and unavailable consideration. Missing player/pick/FAAB evidence does not become zero-asset behavior; legitimate category zeros and directed transfers remain supported.
- Deduplicate reordered participant sets while retaining exact source/transaction identity and rejecting genuine player, pick, FAAB, participant or version conflicts.
- Share coverage and consideration qualifications across League, HQ, Trade and prepared Home partner context. Preserve manager-tenure boundaries, soft historical context, canonical prices/projections, legal lineups, protections and retained FOIS grades.
- No permanent source store, automatic archive repair, historical regeneration or provider loop. Unchanged 2 GiB and 500 ms release gates.
- Contract and coverage: [League/GM historical evidence integrity](docs/LEAGUE_GM_EVIDENCE_INTEGRITY.md). Controlled rendered Chromium is distinct from Scout-independent production and physical-device acceptance.

## v1.21.53 / build 2153 — League and franchise trade context

- Extend shared GM Behavioral Intelligence with bounded completed-trade observations: league activity, original directed assets, exact picks, package shape and repeat counterparties. Distinguish observed zero from partial/unavailable history and unsupported completion clocks.
- Keep franchise actions separate from season-observed current-manager attribution. Current ownership and roster composition do not establish historical preferences; unknown takeover timing and transaction-time ages remain explicit limitations.
- Add concise League identity and progressive franchise insights in the existing League area and Team HQ. Reuse current Dynamic Needs/Surplus for possible conversations; do not replace canonical roster, Market or projection intelligence.
- Carry qualified partner context through shared Trade evaluation, Shop, Trade For, Recommended Trades, adjustments and prepared Home opportunities. History is neutral when absent or unattributed to the current manager, and only breaks otherwise equivalent discovery results.
- Exclude pending/cancelled trades from fallback activity, remove unsupported count-based manager-style labels, and reuse verified season sections without retaining full matchup archives. Reject source changes during section reads rather than pinning mixed publications.
- No new permanent store, provider loop, historical grading, acceptance probability or Home diagnostic panel. Accepted source-age/provenance disclosures, 500 ms liveness and 2 GiB resource gates remain required.
- Audit and source/coverage contract: [League/GM diagnostic audit](docs/LEAGUE_GM_DIAGNOSTIC_AUDIT.md). Browser evidence is Codex-operated isolated Chromium; physical Safari and Scout live acceptance remain separate.

## v1.21.52 / build 2152 — Readable source evidence

- Keep source freshness, retained-refresh warnings and observation ranges concise above named replacement scenarios.
- Preserve every original source timestamp and canonical publication identity in closed Detailed source provenance disclosures on Team HQ/My Team and Trade.
- Add 238/200-observation canonical publisher, actual HTTP and responsive Chromium coverage. No numerical, eligibility, freshness-boundary or storage-policy changes.
- Correct product-browser CI wall-clock budgeting: 15-minute job, 12-minute bounded test step, unchanged test command and assertions.
- Run prepared Home evidence/rendering through the existing manager-read worker boundary, keeping liveness responsive during concurrent reads and cache waits while preserving account/league scope.

## v1.21.51 / build 2151 — Post-Trade Eligibility and Source Aging Integrity

- Re-admit complete proposed rosters through shared canonical availability. Preserve separate PRE/POST identities and status evidence; incoming uncertainty qualifies conditional lineup impact without changing player projections, prices or ownership.
- Age diagnostics at read time from original source observations: Aging from exactly one hour, Stale from exactly six hours. Requalify cached numerical results cheaply; expire higher-level explanations and Home opportunities at evidence boundaries.
- Expose scoped failed-refresh retention separately from source age. Keep valid numbers and clocks, clear failure provenance on successful publication, and reject foreign-publication contamination.
- Present before/after Trade evidence, readable source-clock details and display zero without a negative sign. Preserve existing legal solver/resource guards, bounded caches and no permanent diagnostic store.
- Acceptance contract: [source aging and post-trade evidence](docs/ROSTER_DIAGNOSTIC_SOURCE_AGING.md).

## v1.21.50 / build 2150 — Roster Diagnostic Evidence and Eligibility Integrity

- Reuse canonical player availability to exclude Inactive, Retired and Out from usable replacement coverage while preserving roster identity. Keep questionable, unknown and unsupported status evidence qualified.
- Require compatible, supported scoring and lineup evidence for numeric diagnostics. Genuine zero remains valid; missing scoring, malformed weights, unsupported slots and mixed projection generations withhold dependent conclusions.
- Carry stale/retained projection qualifications through shared team and package evidence, with provisional conclusions and semantic cache invalidation rather than retrieval-clock churn.
- Apply the existing 14-starter/2,048-player diagnostic expansion guard before package and horizon reconstruction; preserve independent trade editing and evidence.
- Replace primary solver dictionaries with named, rounded removal scenarios and readable availability exclusions; use full-width phone evidence cards. No new permanent storage, player projections, Market formula or FOIS regeneration.
- Source controls and independent acceptance: [diagnostic corrections](docs/ROSTER_DIAGNOSTIC_ADMISSION.md).

## v1.21.49 / build 2149 — Dynamic Roster Needs and Replacement Evidence

- Replace fixed QB/RB/WR/TE count-based depth grades with shared league/week/scoring-scoped legal-lineup diagnostics. Separate starter improvement, resilience, current-week strength, conditional expendability and uncertain evidence.
- Verify remove-one effects against a newly optimized disjoint reserve lineup; require observed recipient benefit before labeling conditional expendable depth. Peer references are context, not assumed available offers. No universal surplus or count-only pick surplus.
- Reuse canonical Sleeper projections, legal-lineup memo and existing package/horizon/capacity gates. Add actual pre/post package roster evidence, supported need tie-breaks and consistent My Team/Team HQ/League/Trade/Home explanations. Explicit strategy changes interpretation, never prices or source projections.
- Bound disposable diagnostic results to 12 entries / 2 MiB / 180 seconds with semantic roster/status/projection/scoring identity; no retrieval-clock churn, new permanent store, provider backfill, projection model or FOIS regeneration.
- Current-week diagnostic limitations and unavailable future/long-term evidence remain explicit. Independent acceptance: [diagnostic audit and handoff](docs/DYNAMIC_NEEDS_AUDIT.md).

## v1.21.48 / build 2148 — Trade Opportunity Assessment Integrity

- Separate explicit package adoption from assessment validation. Retain exact assets, original strategy/source evidence, benefits and drawbacks with NOT REVALIDATED qualification and Reevaluate Trade; prior positive/legality claims are labeled previous evidence.
- Bind successful HTTP evaluations to stable semantic canonical source identity. Ownership failures and incomplete/failed reevaluations preserve the package and qualified prior assessment; newer strategy intent rejects obsolete responses.
- Prefer package-specific Home reasons, keep drawbacks and unfavorable labels, and move generic methodology into optional evidence.
- Stop repeated Home focus/visibility/history events safely after context invalidation; clear old cards and provide working Reload Home.
- Preserve shared evaluator, pricing/projections, exact locks, preview/Keep Original/Adopt, bounded cache, historical intelligence and FOIS retained grades. No new store or provider work.
- Independent acceptance: [Integrity correction handoff](docs/HOME_OPPORTUNITY_INTEGRITY_V1_21_48.md).

## v1.21.47 / build 2147 — Home Trade Opportunities

- Add compact hypothetical opportunities after completed League Trade News, with qualified Recommendations separate from editable Trade Ideas and original evaluation labels intact.
- Reuse completed canonical Recommended discovery and explicit Find Trade Ideas; Home never starts a full synchronous search. Up to four distinct supported families, two initially visible, no fabricated padding.
- Scope a disposable 24-entry/2 MiB/15-minute cache to authority, league/franchise, strategy, exact protections and semantic source generations. Reject intervening Market/ownership/projection changes and obsolete pending responses.
- Explore/Edit opens existing preview/Keep Original/explicit Adopt; preserves draft, exact picks, strategy and protections until adoption. No pricing/projection model, permanent recommendation store, provider loop or historical regeneration.
- Independent acceptance: [Home opportunities handoff](docs/HOME_OPPORTUNITIES_V1_21_47.md).

## v1.21.46 / build 2146 — Compact Trade News & Coherent Market

- Show the controlled franchise, record, standing and My Team/Trade actions before Home Trade News. Large packages use a compact preview and an independent Complete Assets disclosure preserving every original player, exact pick and FAAB transfer.
- Prepare canonical normalization off the published rows and commit complete replacement tables. Home captures one detached, checked Market publication for valuation, comparison, ranking and cache identity; changing or incompatible evidence cannot certify a mixed total or bar.
- Carry canonical freshness, fallback, provider/context, source clocks and normalization qualifications into concise card indicators and expanded pricing details. Current values remain separate from historical trade-date grades.
- Preserve rolling 168-hour eligibility, six-card admission, original-trade return, league isolation, existing intelligence and lean storage. No new store, pricing model, provider polling, backfill or FOIS regeneration.
- Independent acceptance: [Home News correction handoff](docs/HOME_NEWS_CORRECTIONS_V1_21_46.md).

## v1.21.45 / build 2145 — Home League Trade News

- Compact completed league trades near Home top, with actual player headshots, exact received picks/FAAB and original-trade return.
- Supported rolling 168-hour status-update eligibility; six-card cap, complete compatible current-Market ranking and qualified unknown-size placement.
- Current-value totals and accessible balance bars stay separate from historical grades; gains/costs and source limitations are available on demand.
- Reuses prepared canonical facts and bounded temporary caches; no new permanent store, provider backfill, pricing/projection model or FOIS regeneration.
- Scope and independent acceptance: [Home Trade News handoff](docs/HOME_TRADE_NEWS_V1_21_45.md).

## v1.21.44 · build 2144 — Beginner Navigation Final Corrections

- Carry the existing validated, league-scoped Market return context into exact-pick dossiers; preserve search, filters, sort, page and selected asset without retaining navigation history.
- Open Home's franchise selector at the existing authorized read-only Team HQ. Keep authenticated Home, selected strategy and owner-only Trade actions scoped to the controlled franchise.
- Intersect recognized free-agent/Taxi search intent with structured availability filters. Contradictory conditions return an honest empty set with accurate counts, without changing prices or ownership.
- Format unavailable and non-finite Commissioner evidence honestly while preserving genuine zero. Keep the My Team trophy beside the identity and the Trade guide beside its heading without smaller text or controls.
- Extend actual authenticated Chromium acceptance to multi-asset/acquired-pick proposals, real evaluation and Balance/preview, pending-response cleanup, objective-preserving Clear Package, reload/history and separate league drafts.
- Preserve Market/projection/Trade/history/FOIS admission contracts and bounded existing session state. No new permanent storage, pricing/projection model, Sleeper write, historical migration or grade regeneration. Independent Scout production acceptance remains separate from controlled browser evidence.

## v1.21.43 · build 2143 — Beginner Experience and Navigation

- Unify Market search, exact player/pick terms, current ownership filters, sorting, counts and pagination. Next advances the actual result set; Browse All clears search/filter scope.
- Open Home’s asset links at the authenticated franchise’s full roster. Show My Team players first, preserve roster/depth/pick facts, and keep the useful shortcuts with advanced evidence on demand.
- Put Trade partner/target and compact asset selection before empty analysis. Keep canonical prices, exact protections and all evaluation/Preview/Keep Original/Adopt behavior; load picker source detail on request.
- Add explicit Start New Trade cleanup for the current draft/objective/temporary protections, preserving selected strategy and other league drafts in bounded session state. Distinguish package-only cleanup that retains a Shop/Trade For objective.
- Compact shared standings into one readable franchise row, retain source facts, ranking/cutoff/tie honesty, and expose canonical champion/streak/movement provenance through shared evidence.
- Link Home to the real Weekly Report, qualify its period state, preserve Market search returns from player dossiers, and serve the existing dossier week-navigation script through the actual application router.
- Clarify selected-franchise, unavailable percentile, scoring-key and historical-scope labels. Use QB red/RB teal/WR blue/TE yellow chips with readable position letters.
- No valuation, projection, scoring, discovery, historical-grade or lineage engine changes; no new permanent store, provider backfill, infrastructure or Sleeper mutation. Trade News and Home Trade Ideas are deferred to a separately scoped release.

## v1.21.42 · build 2142 — Championship Evidence Consistency

- Home, League and My Team trophies now consume the same admitted canonical historical playoff result as season history, rather than deriving a champion from raw bracket rows.
- Require completed historical source-season identity, historical roster membership, distinct admitted finalists and matching predecessor linkage. Current roster membership cannot validate a historical opponent.
- Reuse the existing bounded, generation-aware season cache; corrected or conflicting historical evidence invalidates the trophy decision and warm Home presentation. Preserve raw evidence and retained FOIS grades.
- Preserve valid Day Traders championship provenance, partial-history availability, numeric production weeks, exact lineage, FAAB and all pricing/projection safeguards. No new permanent store, backfill, migration or engine.

## v1.21.41 · build 2141 — Historical Playoff Participant Integrity

- Validate known/resolved playoff participants before set conversion; withhold contradictory championship and placement conclusions while preserving independent history and raw source evidence.
- Apply the same qualification to retained historical results without rewriting checkpoints or regenerating FOIS grades. Preserve valid absent/null participant outcomes, observed advancement and first-round byes.
- Display historical recipient-production weeks in numeric season/week order without changing scoring, role admission or ownership intervals.
- Preserve released production-script delivery, scoped ownership timing, exact lineage, directed FAAB and historical Market gates. No new store, backfill, migration or scoring/projection model.

## v1.21.40 · build 2140 — Historical Source Delivery and Ownership Freshness

- Serve historical-production JavaScript through the released router asset contract; remove the fixture-only static mount. Add bounded requests, visible errors, keyboard retry and obsolete-response protection.
- Carry league-scoped Sleeper retrieval/sync observations from published state into ownership views. Refresh warm timing without new history writes or index rebuilds.
- Withhold malformed/conflicting optional bracket outcome identities at canonical admission and retained reads; preserve independent season content and source limitations.
- Preserve transaction bucket Week 0 in filters and labels. Separate Market source confidence, comparison eligibility, quote clocks and legacy attachment references.
- Link supported FOIS activity references to existing completed-trade dossiers only for the matching league and participating franchise; retain unavailable navigation honestly.
- Preserve exact conversions, directed FAAB, partial production, historical pricing gates and retained FOIS grades. No new store, backfill, scoring/pricing model or Sleeper mutation.

## v1.21.39 · build 2139 — Historical Trade Source Integrity and Readable Insights

- Separate current pick ledger ownership from historical holders; preserve consumed picks, exact conversions and source-scoped observation dates.
- Keep known trades and independent history sections available under partial/missing source evidence. Explain acquired, empty, unavailable, unacquired and malformed periods.
- Repair Archive filters, optional numeric form fields and pagination using source-season franchise/manager facts.
- Preserve original-trade returns across picks, converted players, historical performance and subsequent trades; reject foreign origins.
- Group original consideration by franchise, retain directed FAAB once, expose converted-player endpoints and readable historical evidence links.
- Preserve unknown lineup roles and scoring conflicts; disclose partial recipient-roster production without assigning season totals or exact holding-period benefit.
- Explain provider, units/context, dates, normalization, coverage and rejected raw quotes while preserving historical admission gates.
- Reuse bounded canonical services/caches. No new permanent store, provider backfill, pricing/projection engine, legacy rewrite or historical FOIS regeneration.

## v1.21.38 · build 2138 — Historical FAAB and Score Conflict Integrity

- Show original directed FAAB consideration beside historical players and exact picks, with franchise names and source provenance; do not assign a Market price to FAAB.
- Reconcile all player-week observations before canonical key collapse. Conflicting scores or franchises remain unavailable with retained reasons; identical observations deduplicate, zero remains valid and later source generations can correct scores.
- Limit last-scored ownership to actually scored evidence, distinguish observed season roster snapshots from weekly holdings, retain original quote attachment clocks and describe consumed picks as verified conversions.
- Preserve exact lineage, legacy evidence, bounded caches and the 2 GiB resource contract. No new store, migration, provider backfill, scoring/projection model or FOIS regeneration.
- See `docs/HISTORICAL_FAAB_SCORE_INTEGRITY.md` for contracts, validation and Scout checks.

## v1.21.37 · build 2137 — Historical Trade Timeline Foundation

- Honor explicit My Team full-roster return intent over saved closed disclosure state; keep strategy writes unchanged.

- Preserve exact league/draft/selection identity, original franchise and selecting roster; expose confirmed pick-to-player conversions and directed subsequent transactions through existing historical dossiers.
- Admit historical Market evidence by provider quote/knowledge clocks and compatible canonical units; retain missing pick prices, stale qualifications and original evidence without historical repair.
- Preserve nullable started production, genuine zero, deduplicated player weeks and observed ownership separately from last scoring franchise; qualify uncertain chronology.
- Add bounded generation-aware event/selection reuse, current source-family freshness, completed-trade/pick actions and phone-readable timelines. No new permanent history store, pricing/projection model or FOIS regeneration.
- See `docs/HISTORICAL_TRADE_TIMELINE.md` for limits and Scout acceptance.

## v1.21.36 · build 2136 — Assessment Context & Display Integrity

- Preserve the original evaluated strategy, source identity, rationale and stale qualification through old rendered offer controls, Preview and Adopt; reconcile shared intent before response admission.
- Qualify incompatible retained projection display methods independently of canonical scoring compatibility, preserving original evidence and canonical Sleeper-sourced values even after failed refresh.
- Add real prior-version publisher/current-reader, no-growth and responsive route checks plus multi-tab retained assessment journeys. No new persistent storage, projection model or Market changes.
- See `docs/ASSESSMENT_DISPLAY_INTEGRITY.md` for contracts and Scout acceptance scenarios.

## v1.21.35 · build 2135 — My Team Status & Intent Integrity

- Source availability is enriched before roster-group copies, preserving known injury/status evidence on every roster card and truthful missing states.
- Shared strategy writes occur only on explicit selection or validated migration. Older tabs reconcile shared intent on return and ordinary edits, retaining compatible packages while qualifying strategy-dependent assessments.
- Submitted, optimal/horizon and bye-context player dossiers retain validated My Team section/franchise and supported selected-week context; primary roster and exact-pick returns remain intact.
- Missing TE bonus-stat evidence cannot claim an exact Sleeper source-order display replay. Existing canonical league scoring remains unchanged, and the displayed comparison is explicitly qualified; explicit bonus fields are not counted twice.
- No new projection/scoring engine, permanent preference/roster storage, polling, migration or historical FOIS regeneration. See [correction contracts and Scout handoff](docs/MY_TEAM_FINAL_CORRECTNESS.md).

## v1.21.34 · build 2134 — My Team Evidence & Session Intent

- League/franchise strategy lives separately from temporary Trade proposals in a bounded, account-session-scoped browser cookie; league switching and proposal cleanup preserve the selected goal.
- Partial reserve projections retain a qualified known subtotal without a complete depth grade. Genuine zero remains distinct from missing evidence; holdings alone no longer establish surplus.
- My Team presents roster identity, strategy, supported starter contributions, backup risks and existing record/PF standings first. Roster and capital shortcuts, canonical player/pick dossiers and direct owned-asset Shop actions reuse existing workflows.
- Current-week canonical evidence is pinned across the page; incompatible rollover/scoring/season evidence is withheld. Comparative grades disclose the complete-evidence cohort, and missing Max PF remains unavailable.
- No new projection or valuation engine, permanent roster/preferences store, provider backfill, migration or historical FOIS regeneration. See [audit reconciliation and Scout scenarios](docs/MY_TEAM_INTELLIGENCE.md).

## v1.21.33 · build 2133 — Source-Backed Standings & Playoff Positioning

- Shared Home/League standings rank complete, equal-opportunity/equal-tie-count records by wins then source cumulative Points For, with explicit DTOS provenance. Equal record/PF placements remain unresolved; PA and roster IDs do not break ties.
- Supported standard leagues show a current playoff-position cutoff; complete division rules use per-team indicators. Unknown division/custom rules withhold qualification without hiding valid statistical ranks. This is not final seeding, clinching or a bye guarantee.
- Comparable complete weekly evidence supports separately labeled reconstructed movement. Cumulative source PF/PA remain authoritative. Home consumes the prepared season-matchup semantic identity directly, including historical recovery/corrections.
- Badge explanations expand across the standings panel, with truthful missing-record states and singular streak wording.
- No projection/Market/Trade scoring changes, historical-grade regeneration, storage migration, backfill or new polling. See [contracts, limitations and Scout acceptance](docs/STANDINGS_POSITIONING.md).

## v1.21.32 · build 2132 — Matchup Portrait Readability

- Matchup wrappers, loaded headshots and fallback initials share one contained 28px sizing contract. Shared portraits on other pages remain unchanged.
- Rendered image-state tests cover loaded, loading, failed and missing images; long identity/status text; actual/unavailable projected points; both sides and empty slots at short/tall phone and desktop widths.
- Scoring, Sleeper projections, lineup rules, standings, Trade intelligence and historical persistence are unchanged.
- See `docs/MATCHUP_PORTRAIT_READABILITY.md` for geometry validation, evidence boundaries and Scout handoff.

## v1.21.31 · build 2131 — Phone Matchups & Standings

- Compact side-by-side matchups, authenticated own-matchup-first ordering, full-card activation and preserved selected-week navigation.
- Aligned submitted starters plus visible bench, current IR and taxi; canonical player dossiers return to the same matchup/week. Historical IR/taxi assignments remain unavailable rather than inferred.
- Prominent shared Home/League standings with official records, PF/PA, own-team highlighting, evidence-gated medals/champion badges and completed-game streaks.
- Official ranks and playoff boundaries remain unavailable unless complete rank and standard non-division qualification evidence supports them. No invented win probability or remaining-game estimate.
- Reuses canonical Sleeper projections and prepared optimal-lineup evidence, separately labeled; no new model, polling, storage migration or historical-grade regeneration.
- See `docs/MATCHUPS_STANDINGS_PHONE.md` for acceptance evidence, limitations and Scout handoff.

## DTOS v1.21.30 / build 2130 — Canonical Projection Freshness

Trade uses the actual canonical Sleeper publication identity rather than a constant fallback. Freshness checks cover exploratory alternatives, qualifying results, assessed near misses and Shop returns. Changed evidence qualifies retained assessments without erasing their drawbacks; existing reevaluation and preview/adoption remain explicit.

No new projection model, pricing/ranking change, historical regeneration or storage migration. See [source contract, evidence boundaries and Scout handoff](docs/CANONICAL_PROJECTION_FRESHNESS.md).

## DTOS v1.21.29 / build 2129 — Preview Context, Explicit Shop Scope

Trade previews retain bounded structured assessment context across reload, including exploratory qualification, major drawbacks, confidence/limitations and provenance. Restored evidence is explicitly not revalidated. Balance preserves the completed offer assessment separately from search/loading feedback.

New explicit Shop assets start All eligible teams / Best Overall unless fresh navigation explicitly supplies supported refinements. Compatible same-asset resume preserves chosen scope without duplicate automatic searches. Pricing, intelligence, exact protections and historical records are unchanged.

See [contracts, validation boundaries and Scout handoff](docs/TRADE_PREVIEW_SCOPE.md).

# DTOS v1.21.28 / build 2128 — Simple Trade, Supported Discovery

Build a Trade shows live canonical Market totals, favored manager, gap and a relative-value bar before evaluation. The existing Calculator Balance engine is available alongside the assessment, with preview and explicit adoption. Shop and Trade For begin a bounded search on a fresh valid target entry; refinements retain exact protections.

Trade For and empty Recommended searches can expose supported unfavorable alternatives separately, without changing their labels or promoting missing evidence. Trade For orders qualifying offers by the existing separate-dimension strategy ranking instead of outgoing price alone. Historical grades, valuation formulas and storage remain unchanged.

See [contracts, validation and Scout handoff](docs/TRADE_SIMPLE_DISCOVERY.md).

# DTOS v1.21.27 / build 2127 — Historical Common-Week Evidence

Historical trade evaluation no longer compares production from different weeks. It selects the latest complete eligible common week, discloses earlier-week use and withholds unavailable deltas. Market fairness remains independent.

Existing assessments retain their original grades/provenance; no regeneration, migration or backfill occurs. See [verification and Scout checks](docs/HISTORICAL_EVIDENCE_WEEKS.md).

# DTOS v1.21.26 / build 2126 — FOIS Final Trust & Verification

Front Offices no longer invents a roster-need negotiation angle when none is established. Executive Profiles preserve supported category accomplishments while explaining unavailable overall comparisons. Historical computation is independently verified through the actual source adapters and spawned worker using disposable evidence.

Existing historical grades and ambiguous lineage are retained, not revalidated or regenerated. No scoring, Market pricing, Trade algorithms or storage policy changes.

See [verification, impact limits, future regeneration plan and Scout checks](docs/FOIS_FINAL_TRUST_VERIFICATION.md).

# DTOS v1.21.25 / build 2125 — FOIS Evidence Integrity & Trust

Historical evaluation now preserves compact player eligibility, uses complete legal lineups and admits only comparable decision-time Market evidence. Behavioral support counts independent transactions, shares a two-sided package vocabulary with Trade and withholds unsupported price tendencies. Front Offices separates current holdings from preferences and provides no acceptance probabilities. Executive Profiles expose supported behavioral evidence and readable unavailable states.

Pre-integrity persisted assessments are preserved and visibly labeled **not revalidated**. No historical grades were bulk regenerated. New exact draft-lineage records use league/draft/selection identity; ambiguous legacy records remain untouched. Scoring weights and canonical current prices are unchanged.

See [evidence contracts, preservation policy, validation and Scout handoff](docs/FOIS_EVIDENCE_INTEGRITY.md).

# DTOS v1.21.24 / build 2124 — Reachable Trade Actions

The proposal tray now occupies its own space near the start of the Trade workspace instead of floating over enabled actions. Its asset counts and View Trade action remain available; Recommended discovery stays ahead of it. No proposal, pricing or intelligence changes.

See [reproduction, acceptance and Scout handoff](docs/PROPOSAL_TRAY_VISIBILITY.md).

# DTOS v1.21.23 / build 2123 — Clear User Journeys

Trade evaluation now lands on its current verdict, uses neutral assessment wording, and keeps the major drawback nearby. Recommended discovery appears before manual construction. Shop explicitly defaults to all eligible teams; missing-source guidance names evidence limits and supported next steps.

Exact acquired-pick dossiers resolve available league-specific franchise names, retain complete technical identities, and scroll ownership history locally. Sparse Market selections show an explicit detail-unavailable destination. My Team roster and Calculator Balance have early access links. FOIS movement and trading-style labels withhold unsupported historical conclusions without changing scoring or trade intelligence.

See [audit reconciliation, acceptance and Scout handoff](docs/USER_JOURNEY_CORRECTIONS.md).

# DTOS v1.21.22 / build 2122 — Readable Dossier Status

The actual player-dossier intelligence cards now adapt to a 220px minimum where space permits and stack on narrow phones. Short availability words remain intact at the existing readable value size. The correction targets `article.ai-value > b`, preserving evidence disclosures, technical identifier wrapping and locally scrollable Market tables.

Real `/players/11563` (Bo Nix) and `/players/10225` (McBride) route browser coverage checks status text geometry, labels, numeric values, evidence disclosure and page bounds at 320/375/390px and desktop. No intelligence, pricing, projection, protection or Trade behavior changes.

See [reproduction, visual evidence and Scout handoff](docs/DOSSIER_STATUS_WRAPPING.md).

# Previous release

# DTOS v1.21.21 / build 2121 — Accessible Phone Details

Narrow FOIS leaderboard cards now stack manager identity and score, retain complete names and keep desktop columns readable. GM scores and rankings are unchanged.

Shop protection badges and Calculator protection summaries use native tap/click/keyboard disclosures. Explanations come from the existing exact protection and required-anchor state; opening or closing details never edits the offer or constraints. Exact-pick explanations clarify that other same-round picks remain available.

Player-dossier value cards adapt their width so short status words such as Unavailable stay intact. Long technical identifiers still wrap and structured Market evidence tables still scroll locally.

See [reproduction, validation and Scout handoff](docs/PHONE_VISUAL_CORRECTIONS.md). Responsive Chromium covers 320/375/390px and desktop; physical iPhone/Safari and authenticated live acceptance remain Scout checks.

# Previous release

# DTOS v1.21.20 / build 2120 — Phone-First Front Office

DTOS now uses coordinated charcoal surfaces, green actions, consistent controls and neutral position chips across its existing manager shell. Home separates official records from DTOS strength assessments and puts secondary intelligence behind disclosures. Canonical Market values retain their distinct color and prices.

League medals require a complete, unique Sleeper-reported official rank set. A defending-champion trophy requires the active league’s immediately preceding completed season and resolved championship bracket. Badge explanations work with touch and keyboard; You follows authenticated league membership. Missing historical movement/streak evidence is omitted rather than invented.

Calculator Balance options now appear beside the action with concrete owned player/exact-pick changes and an explicit preview button. Exact protections are inspectable, the protection form stacks cleanly, derived Trade point summaries display sensible precision, and Next Five shows nearby feedback without stale completion messages. No pricing, discovery, balancing, lineup or strategy engine changes are included.

Responsive Chromium covers 320/375/390px and desktop. See [visual evidence, architecture and Scout handoff](docs/PHONE_FIRST_DESIGN.md). Physical iPhone/Safari testing and authenticated live interaction remain independent Scout acceptance.

# Previous release

# DTOS v1.21.19 / build 2119 — Offer-Bound Balancing Feedback

The calculator now clears old balancing completion feedback when an offer edit invalidates its options. Feedback belongs to the exact offer revision and request generation. Equal-value offers correctly disable Balance without suggesting nonexistent previews; rebalancing produces fresh feedback. Exact-lock and strategy changes clear obsolete balancing previews while keeping the offer, protections and unrelated workspace messages intact.

Canonical prices, totals, candidate construction, ownership, acquired-pick identity, Preview / Keep Original / Adopt and Trade integrations are unchanged. Responsive Chromium covers 320/375/390px; physical iPhone/Safari and authenticated live acceptance remain Scout checks.

See [reproduction, validation and Scout handoff](docs/CALCULATOR_STALE_FEEDBACK.md).

# Previous release

# DTOS v1.21.18 / build 2118 — Calculator Balancing Feedback

Balance now immediately shows “Finding balancing options…” beside the action. Package add/remove, incoming protection and exact-lock actions visibly disable during processing. Asset search, evidence, navigation and compatible team/strategy changes remain usable; newer intent cancels the obsolete search. The offer stays intact until explicit adoption. Controls recover after results, empty results, errors or a 45-second timeout.

Canonical Market pricing, ownership, exact picks, balancing construction and Preview / Keep Original / Adopt are unchanged. Responsive Chromium covers 320/375/390px; physical iPhone/Safari remains independent testing.

See [validation and Scout handoff](docs/CALCULATOR_BALANCE_FEEDBACK.md).

# Previous release

# DTOS v1.21.17 / build 2117 — Trade Calculator & Smart Offer Editor

Trade Center now includes a Trade Calculator. Select two teams and use their searchable owned-player and exact-pick lists. Individual canonical Market prices, package totals and the numerical gap update immediately. The favored side is the team receiving more Market value; this is not a guaranteed better trade. Equal totals are approximately balanced. Missing prices remain unavailable, with partial known subtotals and no definitive verdict.

Balance Offer checks a bounded set of owned additions, substitutions, removals and small combinations, then assesses a short list with the existing bilateral evaluator. Market arithmetic remains separate from strategy, legal-lineup contribution, package quality, roster capacity and counterparty plausibility. Poor stuffing and unresolved capacity are disclosed as near misses. Adjustments preview the original/new totals, gap, rationale and drawback; only Adopt changes the current offer. Exact locks and required targets are never automatically relaxed.

Generated/adopted offers open in the same calculator without losing exact assets or compatible constraints. Advanced DTOS analysis uses the existing evaluator separately. Reload, explicit target precedence, ownership, tenant isolation, CSRF and stale-result guards are preserved. No trade is sent to Sleeper.

Responsive Chromium covers 320/375/390px and desktop. Physical iPhone/Safari and authenticated production timing remain independent Scout acceptance.

See [calculator architecture, validation and Scout handoff](docs/TRADE_CALCULATOR_RELEASE.md).

# Previous release

# DTOS v1.21.16 / build 2116 — Explicit Trade Navigation

Selecting a new player in Trade For or Shop now replaces an incompatible saved target and package. Exact protections stay enforced, and feedback explains when the previous package is cleared. Build My Own, Preview, Keep Original and Adopt retain their established behavior.

An ordinary reload keeps a matching adopted multi-asset proposal. Back/forward restores the draft for that browser entry rather than a newer unrelated target. Only the freshly authorized server binding permits restoration; account, league, franchise, ownership and CSRF checks remain intact. Pending pre-navigation searches cannot replace the new selection.

Responsive Chromium covers both workflow directions, same-tab/fresh-tab selection and reload/history at 320/375/390px. No Market, projection, discovery, repair or performance calculation changes are included. Physical iPhone/Safari remains separate acceptance.

See [the explicit navigation audit and Scout handoff](docs/EXPLICIT_TRADE_NAVIGATION_RELEASE.md).

# Previous release: DTOS v1.21.15 / build 2115 — Trade Workspace Navigation Reliability

A canonical Market or projection publication during discovery previously appeared as a different account, league or franchise. DTOS now preserves the mixed-generation rejection, checks the identical request once more when intent is unchanged, and reports an evidence refresh honestly if it continues. Genuine identity mismatches remain blocked and offer a link to the current authorized Trade Center.

Navigation invalidates old search results and their loading-state ownership. Proposals, adopted alternatives, exact locks and Shop/Trade For anchors retain their existing persistence behavior. No authentication, CSRF, tenant isolation, ownership, Market-price, search-budget or trade-quality checks change.

Responsive Chromium coverage includes the Daniels/McBride Cheaper → Build My Own → dossier → Trade For journey at 320/375/390px, plus history, reload, pending requests and isolated workspace bindings. Physical iPhone/Safari acceptance remains for independent device testing.

See [the identity/navigation audit and Scout checks](docs/TRADE_WORKSPACE_NAVIGATION_RELEASE.md).

# DTOS v1.21.14 - Ownership Label Presentation

Ownership-aware player actions from v1.21.13 are preserved. Complete long franchise
names now wrap in Market cards, dossier action status and Live Data ownership.
The rule lives in the rendered shared theme, scoped to ownership labels so
structured evidence tables keep readable columns and local scrolling.
Responsive Chromium covers 320/375/390 and desktop, including unbroken long names.
Canonical facts, player action eligibility, exact picks and Trade behavior are
unchanged. See [validation and Scout handoff](docs/OWNERSHIP_AWARE_PLAYER_ACTIONS_RELEASE.md).

## Previous release: DTOS v1.21.13 - Ownership-Aware Player Actions

Free agents keep their canonical Market value and show Free Agent status without
an impossible Trade For action. My players expose Shop; other-owned players expose
Trade For with the actual owning franchise. Incomplete or conflicting roster
evidence shows Ownership unavailable and disables ownership-dependent actions.
Targeted links are checked before an editor opens, and generation rejects an
unsupported player with an explicit ownership explanation.

Ownership labels and actions update from current league evidence even while a
last-valid Market price generation is retained. Market prices, projections, exact
pick identity and accepted Trade search/repair behavior remain unchanged.
See [validation and Scout handoff](docs/OWNERSHIP_AWARE_PLAYER_ACTIONS_RELEASE.md).

## Previous release: DTOS v1.21.12 - Faster Trade Discovery

Trade search removes repeated legal-lineup and package-construction work. Exact
lineup results can be reused briefly within the same account/session, league and
evidence generation, with strict memory limits. Recommended, Next Five, Shop,
Trade For and repair retain their existing evaluation budgets and quality gates.
Canonical prices, ownership, strategy assessment, explanations, near misses and
exact protections are preserved. Phone loading and stale-result guards remain
intact.

Controlled Day Traders-shaped fixtures preserve every result while reducing
Recommended from 149.4 seconds to a 5.68-second median. A conservative publication
with different projections in all 13 weeks improved from 154.5 seconds to an
18.09-second cold median, 2.55 seconds warm, and 10.79 seconds for Next Five.
These are fixture measurements, not production timing claims. See
[the performance release evidence](docs/TRADE_DISCOVERY_PERFORMANCE_RELEASE.md).

## Previous release: DTOS v1.21.11 - Readable Market Evidence

Full Market Evidence preserves readable column widths and scrolls inside its
bounded container on phones. Brain snapshot identifiers and source fingerprints
continue to wrap completely and remain selectable. Canonical values, ownership,
provenance, projection availability and Trade behavior are unchanged.

## Previous release: DTOS v1.21.10 - Responsive Technical Details

Long Brain snapshot identifiers, hashes and other technical evidence now wrap
inside their disclosures, preserving the full selectable value without widening
the page. Expanded Market details also keep unavailable-value text bounded at
320px. Canonical values, provenance, ownership, projections and Trade behavior
are unchanged.

## Previous release: DTOS v1.21.9 - Canonical Asset Facts

Player dossier Market values now use the same global canonical price as Market
and Trade, even when a player belongs to another franchise or is a free agent.
Front Office context continues to govern ownership, roster fit and trade actions.

Market evidence discloses source generation, source time when available, retrieval
time, freshness and retained-provider fallback. Missing evidence has a readable
reason. Provider normalization and prices are preserved. Sleeper projection
availability now agrees with the selected-week numeric projection panel.

## Previous release: DTOS v1.21.8 - Make It Cheaper Repair Completeness

Make It Cheaper now searches lower-cost substitutions around your current offer
before expanding through bounded package changes. Credible alternatives must cost
less at canonical Market prices and preserve required Shop assets, Trade For
targets and exact protections.

Results show the outgoing cost reduction and explain why a cheaper route could
not qualify, including missing evidence or an exhausted search budget. Alternatives
remain previews until you choose to adopt them. Discovery, strategy assessment
and canonical prices remain unchanged.

## Previous release: DTOS v1.21.7 - Trade Discovery + Repair Reliability

Trade Center searches more credible package constructions when its first pass
finds too few useful choices. Recommended Trades prioritizes varied opportunities
and supports browsing the next five without requiring five results.

Shop retains the selected player or exact pick and can search all eligible teams.
Trade For retains the target's actual owner and explores different acquisition
packages. Adjustments use exact asset constraints and preview alternatives before
you choose to adopt them or keep the original.

Protected assets now remain locked across generation, adoption and repair. Exact
constraint conflicts stay visible, and adopted multi-asset packages survive targeted
page reloads.

Results disclose strategic costs, limited manager-history evidence and evaluated
near misses. Missing required evidence stays unavailable. Market prices, exact
pick identity and the capital/strategy contract remain unchanged.

## Previous release: DTOS v1.21.6 - Trade Center Capital + Strategy Reconciliation

Trade Center now evaluates legal trades involving draft capital under Win Now,
Retool and Rebuild strategies. Recommendations distinguish Market value,
legal-lineup production, future capital, strategy fit and the other manager's
benefit, with strategic costs explained rather than hidden.

Exact pick identity and missing-evidence states remain explicit. Strategy never
changes Market prices, and picks receive no fabricated weekly projections.
The shared evaluation applies to Create Trade, recommendations, shopping,
Trade For, adjustments and alternatives.

## Previous release: DTOS v1.21.5 - Private Operations Inspection

Authorized operators can retrieve predefined, bounded operational evidence over
HTTPS using the existing inspection credential. Diagnostics preserve stored data
and normal product behavior. Detailed operational and security evidence remains
private. This candidate requires release validation before merge or deployment.

## Previous release: DTOS v1.21.4 - Protected Projection Evidence

This narrow correction protects the complete source evidence required by retained
Projection generations. Unsupported legacy evidence remains auditable but is not
presented as supported historical evidence.

Operational generation changes validate both active and rollback evidence before
publication. Prepared reads, scoring precision, explicit missing evidence and
league isolation are preserved. Retention remains bounded by protected evidence.
Detailed operational acceptance evidence remains private.

## Previous release: DTOS v1.21.3 - Bounded Storage Retention

This corrective release bounds redundant operational retention, strengthens
historical cache recovery, and adds bounded storage-growth monitoring.

Supported historical evidence remains available across recovery. Missing
historical evidence stays explicit and is never replaced with current evidence.
Fantasy intelligence semantics and account/league isolation are preserved.
Detailed operational acceptance evidence remains private.

## Previous release: DTOS v1.21.2 - Guarded Storage Recovery

This narrow corrective release strengthens storage-recovery tooling safety and
migration compatibility. Recovery remains explicitly operator-controlled, with
verified rollback protection and separate validation and acceptance stages.

Player projections, FOIS conclusions, historical evidence and account/league
boundaries are unchanged. Detailed operational acceptance evidence remains private.

## Previous release: DTOS v1.21.1 - Bounded Historical Storage

This corrective release reduces redundant historical storage and keeps
unchanged refreshes deduplicated. FOIS conclusions, retained projection evidence,
scoring precision, and account/league boundaries remain unchanged.

Normal product reads remain compatible across the storage update. Historical
evidence availability stays explicit; current evidence is never substituted
for unavailable historical observations. Detailed operational acceptance
evidence remains private.

## Previous release: DTOS v1.21.0 - Season Operations and Final Acceptance

Batch 7 completes DTOS season operations and final integrated acceptance. A
completed league now retains its own season and week when the global NFL clock
moves forward. Projection restoration requires an exact league, season, week
and scoring match, while failed preparation restores the last valid active
state without publishing partial evidence.

Unchanged refreshes and synchronization markers remain deduplicated. Historical
reports, Matchups, Trade, Market, Picks, FOIS and team context retain their
temporal and league boundaries across Day Traders and Super Flexxxin. No new
database schema, durable intelligence store or paid infrastructure is included.

## Previous release: DTOS v1.20.0 - Manager Experience and Reporting

Batch 6 brings full-season Matchups and Matchup Desk, clearer player projections,
shared evidence explanations, Home attention, and weekly league reports into the
manager experience. Team HQ, Market, History and FOIS now distinguish scope,
availability and confidence more consistently across mobile and desktop.

Historical views retain their time boundaries; projected playoff positions and
opponents are not presented as locked results. Existing Trade, Market, Pick and
FOIS intelligence remains unchanged. Cross-league isolation and bounded prepared
reads are preserved. Required release validation and production acceptance are
performed before publication.

## Previous release: DTOS v1.19.1 - Trade Point Presentation

Projected point changes use consistent two-decimal presentation across manual
and generated trade evidence. Canonical precision, scoring, recommendation logic,
missing evidence and true zero are unchanged. This narrowly corrects a display
issue found during Batch 5 live acceptance. v1.19.0 remains immutable.

Batch 5 production acceptance continues; Batch 6 is not started.

# DTOS v1.19.0 - Bilateral Trade and Multi-Horizon Intelligence

Batch 5 connects supported weekly projections and optimal legal lineups to
current-week, Next-N, regular-season, playoff-window and depth/bye evidence.
Actual submitted lineups remain separate. Missing weeks and incomplete lineups
are disclosed rather than extrapolated or filled with zero.

Create Trade, Trade For, Shop Asset, Recommended Trades, Adjust Offer and
alternatives share one bilateral evaluation. Market fairness, package quality,
strategic fit, counterparty plausibility and evidence confidence remain distinct.
Searches are bounded, editable proposals retain ownership safeguards, and no
credible result is fabricated when the evidence does not support one.

Historical storage deduplicates unchanged semantic evidence. No paid
infrastructure, authentication or retired visual-system changes are included.
Implementation checkpoint complete; release gates, deployment and authenticated
production acceptance remain pending. Batch 6 is not started.

## Previous release: DTOS v1.18.1 - Pick Evidence Cache Upgrade

Corrects the production upgrade case where a healthy pre-Batch-4 player cache
deferred missing Pick Market evidence until its next daily refresh. Preparation
now fetches an absent pick family once; a successfully fetched empty family
remains valid and does not trigger repeated requests. Existing provider formats,
quote identities, source freshness and failure isolation remain unchanged.

v1.18.0 remains immutable. Batch 4 production acceptance and restart are pending.
No infrastructure, schema, authentication or retired visual-system changes.

## Previous release: DTOS v1.18.0 - FOIS and Pick Evidence Intelligence

Batch 4 reconciles historical Results and manager tenure, preserves decision-time
process separately from later outcomes, and exposes category quality only where
supported. Missing historical timestamps, Market evidence and roster precision
remain explicit limitations. Results alone cannot produce overall FOIS.

Pick Intelligence preserves original franchise, current ownership and transfer
history. Compatible external Market quotes retain generic/range/exact identities;
unavailable prices are never replaced by internal scores. Ranges remain UNKNOWN
without supported original-franchise evidence. Portfolio context is descriptive,
not a fabricated value grade. Prepared Picks navigation avoids full orchestration.

Semantic histories deduplicate unchanged inputs and retain methodology boundaries.
Release gates and production acceptance are pending. No paid infrastructure change.
Current Visual, DINS and Mirror remain retired. Batch 5 is not started.

## Previous release: DTOS v1.17.2 - Single-Provider Market Coverage

Corrects the shared Market availability boundary: the presence of an incompatible
secondary provider no longer erases a valid FantasyCalc price. The configured
FantasyCalc 12-team/2QB/PPR reference is selected explicitly, not averaged or
converted from DynastyProcess. Independent compatible sources may still form
consensus. Single-provider evidence retains its existing confidence semantics.

Historical-only, explicitly expired/invalid/ambiguous and incompatible feed rows
remain unavailable. No intrinsic, projection, historical or pick fallback is added.
Selection changes carry a methodology boundary. Historical observations, pricing
normalization, infrastructure, authentication and Pick Intelligence are unchanged.

Production coverage acceptance pending. Batch 4 is not started.

## Previous release: DTOS v1.17.1 - Sparse Market Trend Compatibility

Narrow immutable correction for the Batch 3 production acceptance blocker.
The sparse trend reader discarded metadata, allowing raw provider prices and
legacy blended values to produce false volatility. Comparisons now require
explicit matching concept, scale, format and methodology, valid time ordering
and historical knowledge admission. Unproven legacy records remain unchanged
as individual evidence, not numerical trends. Unlabeled current values cannot
silently become historical endpoints. Market/API surfaces expose not-comparable
states and structured boundary reasons.

No historical rewrite, conversion, threshold, infrastructure, authentication,
projection or valuation change. Production acceptance remains pending.
Current Visual, DINS and Mirror remain retired. Batch 4 is not started.

# DTOS v1.17.0 - Player and Market Evidence Intelligence (candidate)

Batch 3 separates source-specific Market evidence, demonstrated production,
current opportunity, weekly expectation and longevity context. Unsupported
long-term intrinsic scalar values and ranks remain unavailable. DynastyProcess
and FantasyCalc are not averaged without a proven shared format contract.

Player, roster, team and trade consumers preserve explicit units, scopes,
missingness and semantic generation. Structured change records distinguish real
evidence movement from the Batch 3 methodology migration. Existing historical
external observations are not rewritten. The retained 57-player panel is a
diagnostic, not a published ranking or fresh production acceptance.

This is an unreleased candidate. Required comprehensive and production gates
must pass before publication. No Batch 4 work, paid infrastructure changes or
restoration of Current Visual, DINS or Mirror is included.

## Prior release

# DTOS v1.16.1 - Reserved League Route Classification

Narrow corrective release for the Batch 2 acceptance diagnostic route. The
authentication middleware now recognizes the exact registered static paths
`/api/leagues/runtime`, `/api/leagues/resources`, and
`/api/leagues/resources/measure` before interpreting a dynamic league ID.

These routes remain authenticated and require an active membership. Measurement
retains CSRF protection. Dynamic league routes, unknown path descendants and
cross-account/franchise scoping retain their existing security checks.

The Linux fixture now distinguishes deferred maintenance (complete last-valid
Market is available) from active replacement (503). A validation-only publication
barrier proves the intended overlap without changing production Market behavior,
artifact semantics, workloads, or timing/memory limits.

No historical backfill, database migration, provider, intelligence, storage or
infrastructure behavior changes. The accepted v1.16.0 evidence remains valid for
those untouched systems. Current Visual/DINS/Mirror remain retired. Batch 3 is
not started.

# DTOS v1.16.0 - Canonical Data Foundation

Master Roadmap Batch 2 establishes shared canonical source evidence and
league-specific derivation. Global NFL production, usage and schedule evidence
are bounded and reusable across leagues; unchanged synchronization does not
append duplicate snapshots. Background workers publish complete source revisions
atomically and preserve prior evidence during interruption.

Sleeper history reconciliation preserves source settings, ownership, regular and
postseason results, transactions and draft identity. Historical franchise reads
exclude unproven future evidence and distinguish exact event times from draft
lifecycle bounds. Missing evidence, ambiguous identities and scoring gaps remain
explicit. No valuation/ranking or FOIS grade recalibration is included.

Coverage limitations: the 2026 production file was unavailable at source review;
no earlier season is substituted. Unsupported scoring bonuses remain incomplete.
Contract/snap/route feeds without verified upstream permission remain unconnected.
Current Sleeper status/depth metadata are not historical status proof. A 0.10-point
source discrepancy in one 2021 standing is retained rather than overwritten.

See docs/BATCH2_CANONICAL_DATA_FOUNDATION.md for evidence and acceptance status,
and docs/BATCH2_CONSUMER_MIGRATION_MAP.md for later consumer migrations. Production
backfill requires dry-run admission. Batch 3 is not started. Current Visual, DINS
and External Visual Mirror remain retired.

## Previous release: v1.15.1 - Lossless Storage Prerequisite

Correct duplicate durable intelligence storage and full-database FOIS preparation
without changing conclusions, historical evidence, ownership, or Trade mechanics.
FOIS observations reference compressed semantic states; projection history shares
unchanged player evidence. Scoped worker publication preserves unrelated leagues.
Explicit maintenance uses bounded compact output, integrity/equivalence checks,
and reversible serialization. No paid storage change or arbitrary history expiry.

Production migration requires separate dry-run admission and the corrected
deployment. See docs/STORAGE_PREREQUISITE_V1151.md. Batch 2 is not started.
Current Visual, DINS and External Visual Mirror remain retired.

## Previous release: v1.15.0 - Trade Center Workspace & Mechanics

Master Roadmap Batch 1 only: one shared, temporary Trade Center workspace across
Create, Trade For, Shop and Recommended entry points. Mobile and desktop use the
same asset selection, review, evaluation and adjustment state. Authenticated
requests carry the existing session protection; ownership errors are separate
from engine failures, and errors do not discard the proposal.

Current ownership and league/franchise isolation remain authoritative. Neutral
Market Balance is separate from bilateral Trade Intelligence. Missing evidence
remains unavailable. No external trade execution, permanent draft storage,
intelligence-methodology change or later roadmap batch is included.

Current Visual, DINS and External Visual Mirror remain retired.

## Previous release: v1.14.1 - Matchups Evidence & Interaction Correctness

Narrow correction to pregame/live/final matchup labels, missing projection
evidence, and existing player-dossier navigation. Pregame projections never
masquerade as live results; absent forecast bounds never become a zero range.
All accepted v1.14.0 visual, isolation, checkpoint reuse and resource contracts
remain unchanged. Current Visual, DINS and External Visual Mirror remain retired.

## Previous release: v1.14.0 — Premium Visual System & UX Coherence

Mobile-first presentation overhaul across Home, Trade Center, Team HQ, Market,
player dossiers, League, matchups, draft capital, history, FOIS, Front Office,
Commissioner Desk and account/settings surfaces. The supplied approved Trade
references govern the platform's visual language, not its production data.

Shared tokens replace competing visual definitions. Compact context switching,
coherent navigation, stronger identity, bilateral offer composition, visible
rank/championship treatment, and real contextual actions improve hierarchy and
usability without changing canonical intelligence. Unknown evidence remains
unknown; no fake values, confidence, trends, trophies, or acceptance odds are added.

Validation exposed repeated canonical-history expansion during startup. One
league-local batch read preserves the exact per-player evidence and 1,000-row
aggregation boundary without retaining a new cache. Validation's default
intelligence stores are now run-owned, and child-process cleanup includes
untagged computation workers. Explicit storage overrides remain authoritative.

Cold FOIS preparation now reuses checkpoint projections within one read-only,
generation-scoped flight. Historical boundaries and all assessment semantics stay
unchanged. Concurrent evidence changes invalidate preparation, and the parent
rechecks the content generation before atomic publication. No private assessment
cache or durable storage is added.

All prior security, multi-league isolation, memory, responsiveness and restart
contracts remain. No dependency, infrastructure tier, or production image-policy
change is included. Current Visual, DINS and External Visual Mirror remain retired.

Candidate validation and production acceptance are pending. Do not interpret this
document as evidence of deployment or a completed production visual audit.

## Prior v1.13.7 — Canonical Team Assessment

Corrects conflicting Team HQ conclusions without selecting a preferred display
label arbitrarily. Existing league-relative Team Intelligence and the canonical
competitive-window engine now supply one shared assessment for roster identity,
Team HQ and unified recommendation outlook. Older results/age/coverage diagnostics
remain explicitly labeled as different, subordinate diagnostics, not team grades.

Projection evidence is pinned to the league's published snapshot and effective
week. Missing bounds are unavailable, never fabricated zeroes. Cache identity
includes projection, Brain and published league generations. Trade selection,
market valuation formulas, historical intelligence and authentication stay intact.

Pre-release validation and production acceptance are pending. v1.13.6 remains the
immutable deployed release until all candidate gates pass. No visual archives or
publication systems are restored.

## Prior v1.13.6 retirement contract (preserved)

This unreleased candidate deliberately retires Current Visual, Live Visual, DINS,
and External Visual Mirror. Prior failed capture runs remain failures; they are
not reclassified as passing application validation. No further capture/publication
workflow is part of release acceptance.

Browser scheduling, screenshot/DOM archives, capture workers, public manifests,
relay transfers and visual publication routes are removed. Production installs no
Playwright or Pillow. Lightweight browser validation uses the separate validation
requirements and does not publish screenshots or private page content.

Read-only semantic inspection, projection reconciliation, accessibility and Trade
interaction regressions remain. Account/league isolation, historical intelligence,
FOIS, Market outputs and stable-boundary artifact reuse remain required. The three
Linux application lifecycle scenarios and canonical release validator remain gates;
actual application memory admission and responsiveness thresholds are unchanged.

Previously reviewed non-visual fixes retain idle FOIS worker reclamation, expired
cache cleanup and bounded calibration iteration without changing intelligence.
Production acceptance requires authenticated multi-league browser journeys, full
smoke and a stable-boundary controlled restart. Historical published release assets
remain immutable. No infrastructure tier or cost change is included.

Validation and production acceptance must finish before this candidate is complete.

# DTOS v1.13.5 — FOIS Active Tenure Continuity

Production acceptance found that a league's historical evidence and newly
calculated scores existed, but current profiles still selected earlier empty
evaluations. Earlier history changed the inferred tenure ID; the one-active-tenure
constraint rejected its insertion while scores referenced that missing ID.

FOIS now reuses the persisted active tenure for the same owner and publishes its
scores with that returned identity. Historical evidence does not imply an owner
change. Takeover snapshots remain immutable, actual ownership changes still close
the previous tenure, and account/league/franchise boundaries remain separate.
No scoring, historical truth, provider, resource, or compatibility rule changes.
No production data is manually repaired. Normal background generation publishes
the corrected current profile; prior evidence remains retained.

Full validation and production acceptance remain required before completion.

# DTOS v1.13.4 — Bounded Restart Evidence Deduplication

The v1.13.3 pre-restart collector correctly rejected a 503,868-node production
payload against its 500,000-node limit. No restart occurred. Normalized provider
rows were duplicated in confidence evidence and canonical valuation records.

This diagnostic-only correction retains those rows once, with exact safe numeric
confidence and freshness fields at their canonical location. All unknown fields,
ordering, privacy checks, publication fences and 64 MiB / 500,000-node bounds remain.
Evidence schema v3 explicitly rejects comparison with the old duplicate layout.

The independent semantic-freshness correction and account/league isolation remain
unchanged. The original v1.13.2 restart cause remains historically unclassified.
Production restart and full acceptance remain required before completion.

# DTOS v1.13.3 - Semantic Freshness and Restart Evidence

Normalized provider confidence now follows DTOS's existing material freshness
tiers. Evidence still loses confidence at legitimate stale boundaries, but small
clock movement within a tier no longer changes canonical confidence. Normalization
contract 1.1 records this correction; no compatibility check is bypassed.

An authenticated, bounded restart evidence command captures retained provider
inputs, Brain/valuation records, projections, calibration and Market rows. It
checks selected identity and generation boundaries, records structural differences
without raw private identities, and atomically retains evidence before rejecting
a moving boundary. These temporary diagnostic files are not publication assets.

The prior v1.13.2 restart incident remains unclassified because its exact source
inputs were not retained. No retrospective causal attribution is made.

Production acceptance and publication must pass before completion is declared.

# DTOS v1.13.2 - League-Scoped Projection Restoration

Production restart acceptance found that the module-level projection service
could briefly expose another league's newer saved snapshot before synchronization.
It now restores using the configured league identity from initialization onward.
If that league has no snapshot, it stays pending instead of borrowing one.

This correction does not alter projection values, scoring, Market compatibility,
storage layout, account authorization, or resource thresholds. A fresh-process
regression reproduces the original failure and verifies independent league
overrides and missing-evidence behavior. Full release and production gates remain
required before completion; v1.13.1 provenance remains immutable.

# DTOS v1.13.1 - Account and League Presentation Isolation

Market and FOIS now cache only reusable league evidence, not authenticated
account controls or session fields. Every response composes its current account
chrome independently. Valuation uses the active league synchronization state.
Player history uses the selected league's name and its own background Sleeper
season reconstruction. Runtime eviction releases current history references;
provider caches and compact checkpoints are preserved without a legacy archive.
Resident leagues receive interval refresh and historical trade-resolution work
using their own state, with cancellation waiting for outstanding writers before
runtime eviction. Inactive account memberships do not create maintenance tasks.

Regression coverage exercises distinct accounts, colliding roster/player IDs,
repeated switching and concurrent requests. All 500 stored memberships are
exercised without eager runtime creation. Global market history remains shared;
league ownership and private intelligence remain scoped. Production acceptance
is required before declaring this corrective release complete.

# DTOS v1.13.0 - Multi-League Intelligence Isolation

DTOS v1.13.0 establishes a fail-closed tenant boundary across the shared
Front Office intelligence stack. Private evidence is accepted only when its
canonical source league equals the active league, including when two leagues
reuse the same roster identifier or manager identity.

Global NFL player identity, market observations, and market-direction evidence
remain reusable across leagues. League-specific ownership, franchise history,
GM behavior, bilateral relationships, and liquidity are isolated. Rejected
cross-league evidence is counted in bounded provenance and never consumed.
Direct loads, repeated switching, and concurrent A/B/C reads remain equivalent
without request-time provider calls, raw history scans, or eager runtime loads.

# DTOS v1.12.9 - Trade Intelligence Historical Upgrade

DTOS v1.12.9 completes the planned season-readiness intelligence chain by
joining the trusted Step 4-7 evidence products into the existing bilateral
Trade Intelligence engine. Current league truth remains decisive: ownership,
legality, neutral value, current roster needs, competitive windows, lineup
impact, and package quality are never rewritten by history.

When support is sufficient, recommendations now explain counterparty package,
asset, positional, bilateral, and market-timing evidence with bounded lineage.
Sparse or contradictory history remains explicitly low-confidence and never
becomes a fabricated acceptance probability. Candidate generation reads the
derived context once, makes no provider calls or raw-history scans, and retains
the established Trade For, Shop Asset, Recommended Trades, Create, Edit, and
Adjust controls.

# DTOS v1.12.8 - Draft Event Timestamp Contract Correction

DTOS v1.12.8 corrects the historical draft timestamp boundary exposed during
v1.12.7 production acceptance. Draft identity is no longer used as temporal
evidence when Sleeper supplies no trustworthy selection time. The deterministic
identity remains preserved in canonical pick lineage while time remains
explicitly unavailable.

Market Trends now safely excludes malformed legacy timestamps from chronology,
milestones, ranges, and horizon calculations. Valid dated observations continue
to produce unchanged Step 7 intelligence, and affected assets return honest
limited evidence instead of HTTP 500. No production-data rewrite is required.

# DTOS v1.12.7 - Market Trends Integration

DTOS v1.12.7 connects the Asset Market to canonical sparse historical market
memory. It derives deterministic direction, magnitude, milestone comparisons,
observed range, volatility, confidence, event context, and bounded league
liquidity without inventing daily history or replacing current market truth.

Global trends use only deduplicated Step 2 observations; private league
transactions remain isolated derived context. Market list summaries are
compact and bounded, asset detail retains full checkpoint provenance, and all
reads perform zero provider calls, history writes, or raw Sleeper scans. The
legacy `MarketHistoryStore` remains runtime compatibility only and is no longer
the Asset Market trend source. Trade recommendations and Step 8 are unchanged.

# DTOS v1.12.6 - GM Behavioral Intelligence

DTOS v1.12.6 adds a canonical GM Behavioral Intelligence layer that describes
observable decision patterns from the trusted historical evidence chain. It
uses transaction-time inputs and manager-tenure attribution to summarize
activity, asset flow, package construction, draft capital, positions, pricing,
competitive-window behavior, trade partners, timing, and recent-versus-earlier
patterns with dimension-specific samples, coverage, confidence, and bounded
evidence references.

The model remains descriptive rather than psychological or zero-sum. Process
quality and later Outcome stay separate, missing historical market evidence is
never filled with current value, and contradictory or sparse evidence remains
explicit. Profiles are prepared in the existing isolated FOIS lifecycle with
deterministic generation-aware reuse and no new provider calls or raw-history
scans. FOIS scoring, Brain semantics, Trade recommendations, Market Trends,
offers, and UI are unchanged.

# DTOS v1.12.5 - FOIS Front Office Brain Unification

DTOS v1.12.5 establishes one canonical Front Office evidence layer for FOIS,
Front Office Intelligence, and the DTOS Brain. The shared contract carries
Step 4 transaction-time Process, later Outcome, confidence, maturity, evidence
references, and source-generation lineage while keeping those concepts
separate and honestly unavailable when historical support is incomplete.

Evidence is assembled during the existing isolated background FOIS lifecycle
and published as a bounded generation-aware snapshot. Front Office and Brain
requests consume that snapshot without raw-history scans, provider calls, or
backlog reconstruction. Current recommendation scoring is unchanged, manager
tenures do not inherit prior-owner decisions, and league data remains isolated.

# DTOS v1.12.4 - Historical Transaction Intelligence

DTOS v1.12.4 turns canonical historical facts into trustworthy decision
evidence. It evaluates both franchises in a historical trade using only the
event boundary, contemporaneous franchise states, and legitimate at-or-before
global market evidence. Process and Outcome remain separate, so sound process
can have a poor later result and questionable process can benefit from luck.

The derived contract retains explainable dimensions, independent confidence
and maturity, evidence references, source generations, and method versioning.
Unknown values are never treated as zero or replaced by current values. A
bounded asynchronous backlog service is deterministic and idempotent, performs
no provider calls or Step 4 raw-history scans, and does not change FOIS, Brain,
current Trade Intelligence, Market Trends, or product presentation.

# DTOS v1.12.3 - Historical Franchise State Reconstruction

DTOS v1.12.3 adds the canonical derived state layer required before historical
decision intelligence can be graded. Given a league, franchise, and explicit
historical boundary, it reconstructs the facts and evidence available at that
time: historical rules, roster and pick ownership, record, weekly lineup and
production evidence, sparse global market values, and a confidence-calibrated
competitive-window result.

The service reverses only later canonical events from provider-backed season
state, exposes deterministic pre/post pairs and diffs, and never substitutes
today's roster, market, standings, picks, or later outcomes. Missing dimensions
remain partial or unavailable rather than zero. It adds no provider calls,
HistoricalStore dependency, per-league market history, or permanent franchise
snapshot warehouse, and it does not grade trades, waivers, drafts, or GMs.

# DTOS v1.12.2 - Event-Relevant Global Player Market Memory

DTOS v1.12.2 establishes sparse, durable global player-market memory on the
canonical Historical Intelligence contract. Meaningful player events and
milestones can preserve provider-backed market evidence for reuse across
leagues, while private league transactions remain isolated references.

Milestones are limited to the persisted Relevant Player Universe. Supported
global events evaluate only a bounded, explainable player neighborhood, and a
relationship alone never forces storage without material change. Durable reads
retain provider, normalization, confidence, and trigger provenance, survive
restart, and enforce at-or-before no-hindsight lookup. Historical backfill is
bounded and idempotent and records no current value as historical evidence.

This release builds memory only: current Asset Market output, FOIS scores,
trade recommendations, rankings, and presentation contracts are unchanged.

# DTOS v1.12.1 - DINS Public-Origin Serialization Correction

DTOS v1.12.1 corrects the DINS producer boundary used by authenticated
production capture. The browser may reach DTOS through a private loopback
transport, but publication-safe structured artifacts now represent only
application-owned URLs through the explicitly configured public origin.

The correction preserves URL paths, queries, and fragments, leaves external
resources unchanged, and does not perform blanket text replacement. A
surviving loopback reference still fails the unchanged packager. Historical
Intelligence, Asset Market semantics, visual presentation, authentication, and
production data are unchanged.

# DTOS v1.12.0 - Canonical Historical Intelligence Contract

DTOS v1.12.0 begins the Season-Readiness Intelligence program with one neutral
historical-intelligence contract. Reconstructable Sleeper facts remain in the
existing disposable completed-season cache and are normalized into stable,
league-scoped events only when read. Sparse public market checkpoints remain a
separate global contract and never expose private league packages or manager
behavior.

The new service supports bounded league, franchise, player, season, transaction,
identity, and event-time queries; active/completed-season deduplication; honest
timestamp provenance; and explicit no-hindsight checkpoint selection. It adds no
database or permanent full league archive and does not change FOIS scores,
recommendations, Market trends, historical trade grading, or visual behavior.

# DTOS v1.10.71 - External Visual Mirror Authenticated Source Contract

DTOS v1.10.71 completes the secure source boundary for the External Visual
Mirror. Render acquires the accepted projection audit through the existing
inspection credential, validates it, and publishes a credential-free snapshot
atomically with the matching Current Visual generation. GitHub never receives
the production credential and no authentication material enters public output.

The protected audit endpoint remains anonymous HTTP 401. Projection semantics,
Current Visual rendering, DINS, Asset Market, and authentication policy are
unchanged. Deterministic authentication failures now fail fast instead of being
retried as warming.

# DTOS v1.10.70 - DINS DOM-Origin Serialization Correction

DTOS v1.10.70 corrects the DINS producer boundary that previously serialized
browser-resolved application links with the loopback capture origin.

Internal application anchors are rebased during structured DOM extraction using
the existing `DTOS_PUBLIC_URL` contract. Paths, query strings, and fragments are
preserved; external origins remain unchanged. The DINS packager remains fail
closed, and product UI, Asset Market semantics, and infrastructure are unchanged.

# DTOS v1.10.69 - Symbol Rendering Correction

DTOS v1.10.69 is a surgical rendering correction for the visual status system.
Trophy and fire pseudo-elements now use direct Unicode glyph content, preventing
Python string parsing from turning CSS escapes into control characters. Champion
and HOT-state semantics, podium styling, page composition, and all intelligence
contracts remain unchanged.

# DTOS v1.10.68 - Visual Fidelity Correction

DTOS v1.10.68 changes the rendered manager experience, not merely its colors.
Home now opens as a front-office briefing, franchise pages lead with identity
and recognizable starters, League rankings use a real podium hierarchy, and
Market presents players and picks as ranked dynasty assets.

Trade Center receives the reference-driven correction: offers visibly separate
send and receive packages, emphasize player imagery and values, explain both
sides of the deal, and present one clear next action. The approved screenshots
define the visual grammar; their phone and editor overlays remain excluded.

No valuation, trade intelligence, Sleeper, projection, ownership, historical,
authentication, artifact, or infrastructure semantics change in this release.

# DTOS v1.10.67 - Site-Wide Visual System

DTOS v1.10.67 introduces a cohesive visual foundation across the existing
manager product. It applies a premium dark, layered presentation with clearer
hierarchy, denser decision cards, consistent actions, stronger responsive
behavior, and an improved five-destination navigation shell.

Trade Center receives the most focused presentation update: its four existing
workflows, bilateral packages, market values, confidence, evidence, and honest
empty states now read as one coherent decision surface. No trade logic, market
semantics, route, production data, or intelligence output changes.

The supplied mobile images informed visual language only. Their phone status
bar and editor/share overlay controls are deliberately not part of DTOS.

# DTOS v1.10.66 - Artifact-Build Provenance Identity Stability

DTOS v1.10.66 corrects a retained-artifact provenance mismatch observed after
the v1.10.65 controlled restart. Compatible reuse restored the exact market
generation with zero construction, but the loader labeled that immutable model
with the current live Historical Memory identity instead of the identity stored
when the artifact was built.

Compatible loads now restore the persisted artifact-build identity atomically
with the model, generation, and health metadata. Directory and market-health
responses keep `artifact_build` scope; search and detail retain their current
`live_store` contract. Missing provenance fails safely as an incompatible
artifact. Semantic compatibility, output, request-time work, and all resource
thresholds remain unchanged.

# DTOS v1.10.65 - Authenticated Production Smoke Contract

DTOS v1.10.65 corrects the production smoke contract exposed after v1.10.64
successfully deployed with authentication enabled. Anonymous protected pages
were correctly showing the sign-in surface, but the older validator treated
that security behavior as product content and failed before authenticated
acceptance could begin.

The smoke harness now proves both boundaries independently. Anonymous private
HTML and API requests must receive the canonical authentication-required
behavior. Product requests then reuse the established inspection-safe header
context, which resolves a deterministic active league and mapped franchise
through the same account middleware without creating a durable session or
using a real account password. Public health and inspection routes remain
anonymous, credentials never enter diagnostics, and an incomplete production
fixture fails closed.

No product route or authentication behavior changes. The v1.10.64 Front Office
contract, direct historical-leader aggregation, persistent bounded compute
lane, one web worker, and all latency and memory thresholds remain unchanged.

# DTOS v1.10.64 - Front Office Context Contract

DTOS v1.10.64 corrects the canonical production smoke expectation exposed
after v1.10.63 successfully verified the authenticated Trade manager contract.
The production account boundary intentionally normalizes protected Front Office
and Trade queries to the active membership's true mapped franchise; the older
roster-by-roster smoke loop incorrectly treated each explicit query as a
session-persistent analytical View As mutation.

The validator now applies the same authenticated identity rule to HTML and API
surfaces while retaining explicit request-local selection in unscoped local
validation. No product route, account membership, session, or intelligence
behavior changes. Regressions prove league-switch, logout, multi-user, and
private-context isolation.

Archive-warmed Linux validation also identified a real memory-margin failure in
the canonical historical-leader read. The read previously constructed every
record type for the season, copied the filtered player-week records, and then
retained only 40 aggregate rows. It now aggregates directly over the canonical
Sleeper season facts, preserving identical leader semantics with bounded
temporary state.

Repeated canonical warming traces then proved that FOIS computation was
isolated but its parent-side snapshot compaction and process-pool pickling could
still monopolize the web interpreter. The existing single persistent spawn
worker now receives only a bounded canonical-cache control contract and loads,
validates, compacts, and evaluates that immutable input in the child. This
preserves one web worker, one compute lane, existing FOIS semantics, and the
current deployment tier without tying process count to league memberships.

The v1.10.63 Trade correction, homepage action, FOIS process isolation,
180-second watchdog, Windows-safe progress publication, and all latency and
memory thresholds remain unchanged.

# DTOS v1.10.63 - Authenticated Trade Manager Context

DTOS v1.10.63 corrects the canonical production smoke contract after v1.10.62
proved that authenticated inspection identity already supplied an authorized
active league and mapped franchise. The older validator incorrectly required
the resolved manager to choose that franchise again.

The validator now proves the stronger identity contract: a fully configured
inspection membership must control its exact mapped roster, while unresolved
contexts must expose the explicit chooser and may never guess a roster. Trade
templates, manager resolution, authorization semantics, and product output are
unchanged.

The v1.10.62 homepage action, Windows-safe progress artifacts, compact persistent
FOIS worker, 180-second watchdog, and all latency and resource thresholds remain
unchanged.

# DTOS v1.10.62 - Homepage Primary Action Presentation

DTOS v1.10.62 corrects a narrow canonical smoke-detection mismatch discovered
after v1.10.61 deployment. Signed-out `/` correctly redirected to the shared
sign-in page and rendered its real, accessible `Sign in` submit action, but the
validator required an exact CSS class string and did not recognize the existing
semantic primary-action marker when an additional `btn` class preceded it.

The release recognizes the established semantic action contract while still
requiring an actual anchor or button. Authenticated Home continues to present
`Open Team HQ`; account authorization, multi-league behavior, FOIS process
isolation, the 180-second outer validation watchdog, and every product latency
and memory threshold remain unchanged.

Pre-release validation also exposed two infrastructure scheduling boundaries.
Run-scoped progress evidence now uses cross-process reader/writer serialization,
unique same-directory atomic snapshots, and bounded cleanup on Windows and
Linux. Canonical HTTP timing begins when the client performs the socket
operation; progress-evidence publication remains separately recorded.

FOIS retains one web worker and one isolated compute worker, but prewarms that
spawned worker before request acceptance and reuses it for bounded immutable
work units. The subprocess input contract includes only fields FOIS actually
consumes, reducing the production-shaped payload from about 18.4 MB to about
184 KB while strict regressions prove identical FOIS scores and clean shutdown.

# DTOS v1.10.61 - Account/Onboarding Inspection Presentation

DTOS v1.10.61 corrects the shared presentation contract for the six account and
onboarding surfaces. Their normal and deterministic inspection renderings now
use the same reduced account shell, canonical page header, and real semantically
identified primary action across desktop, tablet, and mobile.

The release does not alter authentication, account persistence, multi-league
membership, league-series grouping, Asset Market semantics, or Historical
Memory. Production DINS publication uses the public DTOS origin so generated
artifact identities never contain an internal capture address.

## Previous release

DTOS v1.10.60 introduced the Multi-League Onboarding Authorization Boundary.

# DTOS v1.10.60 - Multi-League Onboarding Authorization Boundary

DTOS v1.10.60 corrects the authorization boundary that previously rejected a
legitimate newly discovered league before the account onboarding handler could
verify Sleeper ownership. The exception is deliberately narrow: authenticated
onboarding/import and established-membership activation reach their handlers,
while ordinary private league routes retain the existing membership gate.

The release also presents a continuing Sleeper dynasty as one league series.
Grouping uses authoritative `previous_league_id` continuity, preserves all season
league IDs, never groups by name alone, and promotes future seasons without a
hardcoded terminal year. Account memberships remain normalized one-to-many and
league runtimes remain lazily bounded rather than loading every membership.

# DTOS v1.10.59 - Accounts, Identity, and Sleeper Onboarding Foundation

DTOS v1.10.59 introduces the secure consumer identity foundation described by
the Product and Intelligence Blueprint. DTOS accounts are distinct from public
Sleeper identities. A user can create an account, save one-time recovery codes,
link a resolved Sleeper username, discover eligible leagues, and select the
franchise associated with that identity. DTOS does not claim that Sleeper proves
account ownership.

Private league and manager surfaces now derive their context from an opaque,
durable, server-side session. Credentials use Argon2 hashes; session tokens and
recovery codes are stored only as digests; browser mutations use CSRF controls;
and logout or recovery invalidates prior sessions. The release adds only compact
account, identity-link, membership, session, and audit state. It does not restore
HistoricalStore or duplicate provider, market, or intelligence payloads.

## Previous release

# DTOS v1.10.58 - Asset Market Front Office Link Correction

DTOS v1.10.58 narrowly corrects Asset Market directory navigation when no
league-scoped Front Office context is present. Optional context is now omitted
instead of serialized as an invalid empty integer, while explicit manager
context and selected assets remain intact. Market intelligence, Trade Center,
and the v1.10.57 DynastyProcess correction are unchanged.

## Previous release

# DTOS v1.10.57 - DynastyProcess Player Interaction Correction

DTOS v1.10.57 narrowly corrects deterministic DINS interaction transport for
external attribution links. Player pages already linked DynastyProcess to its
official GitHub repository; inspection now preserves that origin instead of
replaying the pathname against DTOS and reporting a false HTTP 404. No provider,
valuation, player-dossier, Asset Market, or Trade Center behavior changes.

# DTOS v1.10.56 - Mobile Trade Asset Browser Filtering

DTOS v1.10.56 narrowly corrects the Trade Center asset-browser visibility contract. Roster and position filters now control computed rendering—not only semantic attributes—at desktop, tablet, and mobile breakpoints. The v1.10.55 controlled-manager, bilateral intelligence, market-value, balance, repair, and mobile presentation contracts remain unchanged.

# DTOS v1.10.55 - Controlled Manager Trade Discovery and Mobile Experience

DTOS v1.10.55 makes Trade Center explicitly manager-controlled and league-scoped. Missing identity now produces a franchise-selection state instead of silently selecting roster 1. Trade For reports bounded search evidence and honest closest-path guidance without weakening bilateral quality. The mobile builder is asset-first, with roster browsing, player and pick identity, positional market context, one-tap asset selection, and an immediate neutral market-balance view that remains separate from DTOS recommendation logic.

# DTOS v1.10.53 - Trade Builder and Repair Intelligence

DTOS v1.10.53 makes the Trade Center behave like a bilateral negotiation tool.
Repair intelligence now treats the requested receive-side asset as immutable for
Make This Trade Work and Alternative Construction. Only a clearly labeled
Alternative Target result may change that goal. Player and pick selection also
uses one canonical neutral-market rank/value identity, while proposal responses
show the actual send/receive construction and useful next steps when no honest
path exists.

The release introduces no request-time provider work or permanent generated
trade storage and preserves the v1.10.52 manager-read scheduling boundary.

## Previous release

# DTOS v1.10.52 - Trade Center Accessible Name Correction

DTOS v1.10.52 narrowly corrects the accessibility gate that blocked v1.10.51
inspection publication. DINS now follows native disclosure visibility semantics,
and dynamic asset-removal controls identify the exact player or pick they remove.
Trade workflow pages no longer generate full recommendation intelligence before
the manager acts, while legitimate Trade computations run without monopolizing
unrelated request scheduling.
Front Office and Trade manager views now share the same non-blocking execution
boundary while preserving their canonical intelligence and rendered output.
Trade values, recommendations, ownership-aware entry, and assisted workflows are
unchanged.

## Previous release

# DTOS v1.10.51 - Trade Center Recommendation Quality and Ownership-Aware Entry

DTOS v1.10.51 makes the Trade Center stricter and more useful without changing
the canonical neutral value foundation. Recommended trades now require coherent
bilateral value, roster effects, package quality, and counterparty rationale.
Player and pick pages open the correct ownership-aware workflow, while Create
Trade proactively offers a small set of editable, calculated alternatives.

## Previous release

# DTOS v1.10.50 - Trade Center Value Integrity and Workflow Conformance

DTOS v1.10.50 corrects the value and workflow defects found through direct
manager use of the v1.10.49 Trade Center. Neutral Value Fairness now consumes
the canonical market layer without silently blending in team fit or unsupported
intrinsic conviction. DTOS opinion remains visible as a distinct strategic
signal, and Superflex replacement scarcity remains a separate bilateral gate.

Future picks now use their original franchise, projected early/mid/late range,
confidence, round, and time horizon when synchronized evidence supports that
classification. Unknown picks remain honestly uncertain and no longer receive
an automatic premium outcome.

The manager workflow now supports multiple players and picks on both sides.
Edit Trade retains the complete proposal; Adjust Offer invokes bounded assisted
generation; and rejected proposals expose calculated repair, alternative
construction, and alternative-target options only when legitimate candidates
exist. Assistance reuses one cached workspace and performs no provider calls or
Asset Market construction.

## Previous release

# DTOS v1.10.49 - Trade Center Overhaul and Bilateral Trade Intelligence

DTOS v1.10.49 establishes the first production Trade Center foundation described
by Product & Intelligence Blueprint v0.5. Create Trade, Trade For, Shop Asset,
and Recommended Trades now share one deterministic bilateral evaluation contract.

The evaluator keeps fairness, strategic fit, counterparty plausibility, package
quality, best-for context, and qualitative confidence distinct. Generated ideas
must clear legality and counterparty gates, while manual proposals remain
analyzable and explicitly identify non-executable constructions. Both rosters are
compared using the same league-configured Optimal Legal Lineup baseline.

## Previous release

# DTOS v1.10.48 - External Visual Mirror Semantic Validator Correction

DTOS v1.10.48 removes a stale External Visual Mirror validator dependency on
the exact prose phrase `Sleeper canonical projection`. Matchup mirror packaging
now consumes the structured browser-capture contract already used to reconcile
semantic projection nodes, exact values, availability, team totals, and the
manager-facing `Pregame projection` label.

The accepted UI and all projection intelligence remain unchanged. The mirror
still fails closed for missing nodes, numeric or availability mismatches, wrong
manager semantics, and legacy DTOS projection labels.

## Previous release

# DTOS v1.10.47 - Live Visual Text-Normalization Contract Correction

DTOS v1.10.47 corrects the browser presentation reconciliation boundary exposed
by production Live Visual. CSS-transformed casing is normalized for the exact
manager-facing `Pregame projection` label, and surrounding team-name whitespace
is trimmed without fuzzy matching.

Canonical values and availability remain strict: numeric mismatches still fail,
unavailable projections cannot render as zero, and legitimate zero remains a
real projection. No intelligence, storage, lifecycle, or UI-copy behavior
changes in this corrective release.

## Previous release

# DTOS v1.10.46 - Matchup Label/Inspection Contract Correction

DTOS v1.10.46 corrects the inspection boundary for matchup projections. The
manager-facing label remains `Pregame projection`; a stable semantic DOM field
now lets Live Visual validate canonical availability and exact values without
requiring provider-specific wording in the visible interface.

The release adds real rendered-route regression coverage and preserves all
Projection, Brain, Asset Market, FOIS, Trade Intelligence, history, storage,
availability, responsiveness, and restart semantics from v1.10.45.

## Previous release

# DTOS v1.10.45 - Matchup Presentation Contract Correction

DTOS v1.10.45 aligns the matchup page's canonical projection rendering with the
strict Live Visual and Live Inspection contract. Projection values use one
shared two-decimal presentation boundary, while missing projections remain
explicitly unavailable and legitimate projected zero remains a real zero.

The correction is presentation-only. It preserves the v1.10.44 UX foundation,
all intelligence semantics, Live Visual coverage and responsiveness, durable
storage, sparse market memory, and HistoricalStore retirement.

## Previous release

# DTOS v1.10.44 - UX Foundation Polish / Correctness

DTOS v1.10.44 refines the deployed UX Foundation with honest evidence states and
manager-first hierarchy. Missing, unsupported, unknown, and not-yet-started
evidence no longer appears as a meaningful numeric zero. Preseason Home and
League views now present compact briefings instead of fake current-season
records, and Matchups lead with canonical pregame projections until scoring
begins.

Deep Market evidence now leads with value and recommendation context while
technical identities remain available in collapsed disclosure. Team roster
rooms reuse the established Sleeper headshot presentation with safe fallbacks.
The release does not change navigation, valuation, Brain, Projection, FOIS,
Trade, history, or Global Sparse Market Memory semantics and adds no permanent
presentation warehouse.

## Previous release

# DTOS v1.10.43 - UX Foundation

DTOS v1.10.43 established the first post-infrastructure product implementation
batch. It turns the application shell into a manager experience with five primary
destinations: Home, My Team, Trade, League, and Market.

Home is now a front-office briefing rather than an Asset Market directory. My
Team leads with the starting lineup and DTOS assessment, League collects the
league-wide surfaces, Market begins with search and meaningful movement, and
matchups present actual scoring, canonical projections, production rank, and a
clearly labeled evidence-bound storyline. Existing Brain, FOIS, valuation,
history, storage, projection, and artifact semantics remain unchanged.

# DTOS v1.10.42 - Actual ChatGPT-Retrievable Visual Transport

DTOS v1.10.42 publishes the already-verified rolling Current Visual generation as
ordinary GitHub Pages HTML, JSON, and PNG content. The stable discovery page is
human-readable without JavaScript and links directly to the current manifest and
representative desktop/mobile images.

The Pages payload is assembled in an Actions runner from the allowlisted DTOS
current generation, never committed to Git, and uploaded with one-day artifact
retention. Atomic Pages deployment keeps the previous verified site available
until the replacement succeeds. This delivery-only correction leaves capture,
FOIS, Brain, Asset Market, history, and Global Market Memory behavior unchanged.

## Previous release

# DTOS v1.10.41 - Native ChatGPT Visual-Mirror Accessibility

DTOS v1.10.41 completes the consumer-facing Current Visual transport. A generic
web client can start from `/current-visual`, discover the current deployment and
visual generation, fetch an `application/json` manifest, and retrieve allowlisted
current PNGs without authentication, cookies, JavaScript, release numbers, or
generation identifiers.

The delivery boundary uses stable human-readable paths, supports safe GET/HEAD
probing, exposes native `image/png` with inline disposition, and revalidates the
rolling manifest without making capture, provider, history, market, or write calls.
Atomic candidate promotion, current-only retention, private-league exclusion, and
all v1.10.40 responsiveness behavior remain unchanged.

## Previous release

# DTOS v1.10.40 - Post-Restart Live Visual Responsiveness

DTOS v1.10.40 prevents post-restart Live Visual work from being scheduled
against an incomplete Asset Market identity. Compatible captures now remain
current across restart, and new capture work begins only after the canonical
market generation is atomically available.

The correction preserves one Uvicorn worker, isolated browser capture, atomic
visual publication, existing memory and latency gates, and all v1.10.39 product
contracts.

## Previous release

# DTOS v1.10.39 - Live Visual Process Isolation

DTOS v1.10.39 makes Live Visual capture genuinely background work. Each browser
flight now runs in one bounded, lower-priority subprocess, leaving the single
Uvicorn interpreter available to accept health, market, FOIS, history, and
current-mirror requests. A compact private file contract returns presentation
metadata; timeout and failure cleanup terminate the complete browser tree.

One transient browser failure receives one tracked retry. Incomplete flights
remain honest and cannot replace the last verified rolling generation. Complete
flights retain atomic promotion, direct native PNG delivery, SHA-256 and decode
verification, and the public HTTPS origin correction introduced in v1.10.38.

## Previous release: v1.10.38 - Public Current Visual Origin Correction

DTOS v1.10.38 makes the rolling current-product visual mirror consumable from a
future public client. Durable manifests now identify PNGs with environment-neutral
relative paths. The inspection boundary derives absolute URLs only from DTOS's
validated external HTTPS origin, while Playwright retains its independent loopback
capture origin.

The correction preserves current-only retention, atomic candidate publication,
direct native `image/png` responses, SHA-256 and dimension verification, and safe
read-time compatibility for the retained v1.10.37 manifest. Production rejects
loopback, localhost, unspecified, and private-IP public origins without trusting
arbitrary forwarded host headers.

## Previous release: v1.10.37 - ChatGPT-Inspectable Rolling Visual Mirror

DTOS v1.10.37 completes a stable, externally inspectable current-product visual
contract. A tiny manifest discovers the current verified generation without knowing
the release number, and every capture has a direct native PNG URL with size, SHA-256,
dimensions, page identity, viewport, and deployment provenance.

Candidate generations are staged and verified before an atomic pointer update. The
last working generation remains available on failure, and the prior rolling generation
is retired only after successful promotion. Live Visual bytes are linked when the
filesystem supports it, keeping rolling storage bounded without duplicating DINS.

v1.10.36 made FOIS a current league GM leaderboard: one canonical active
profile for each current GM, deterministically ranked, with confidence,
completeness, supported evidence, strengths, and improvement areas visible.
Meaningful historical snapshots and prior tenures remain available only beneath
the applicable GM profile.

The versioned confidence contract distinguishes reliability from evidence
coverage, excludes unavailable dimensions from performance scoring, and keeps
trade process separate from later outcome. FOIS continues to use reconstructible
Sleeper facts, canonical Brain context, and compact DTOS-owned snapshots without
restoring HistoricalStore or introducing request-time provider calls.

## Validation focus

- Ten current Day Traders GMs produce exactly ten current canonical profiles.
- Full 2021–2025 history and current/pending 2026 semantics remain honest.
- Active-tenure identity survives season league IDs and franchise renames.
- Desktop/mobile leaderboard and GM history drill-down remain semantically distinct.
- Generation remains idempotent, nonblocking, multi-league isolated, and compact.

---

# DTOS v1.10.35 - Historical Resolution Bulk Reuse & Request Responsiveness

DTOS v1.10.35 makes unchanged historical trade-market replay inexpensive by
validating durable results in a bounded bulk SQLite read. It retains exact
resolution semantics while exposing request-entry, event-loop lag, and replay
resource diagnostics needed to verify production responsiveness.

## Validation focus

- Exact durable replay equivalence and partial-miss provider fallback.
- O(1) replay connection use with three indexed result queries.
- One-time checkpoint and observation decoding in bounded batches.
- Strong file-generation checksum reuse for non-blocking warm historical identity reads.
- Retained Asset Market availability and liveness during historical resolution.

---

# DTOS v1.10.34 - Live Visual Stale Capture Refresh Correction

DTOS now refreshes stale required Live Visual evidence through the documented
on-demand metadata path. Current compatible captures remain deduplicated, while
stale or missing registered captures queue exactly one replacement and publish
their image, metadata, identity, and artifact hash together. External Visual
Mirror publication still fails closed until every required capture is current.

## Previous release: v1.10.33 - Historical Resolution Replay Resilience & Durable Reuse

DTOS now restores compatible historical trade resolutions directly from compact
Global Market Observation references. Unchanged replay no longer depends on a live
historical provider or disposable provider cache. Final unavailable evidence is
recorded compactly, while provider rate limits remain explicit retry-pending states
without fabricated grades, current-market fallback, or permanent provider archives.

## Previous release: v1.10.32 - Historical Trade Gradability Accounting Correction

DTOS now assigns every completed historical trade exactly one process-gradability
state. FAAB-only trades remain canonical completed activity with unavailable
execution-time market valuation and an explicit not-gradable classification; no
FAAB-to-market conversion is introduced. Summary invariants fail closed if either
execution-value or process-gradability counters do not balance to the canonical
completed-trade total. Global Sparse Market Memory, provider resolution, FOIS
scoring, and HistoricalStore retirement remain unchanged.

## Previous release: v1.10.31 - Sparse Historical Trade Market Matching

DTOS v1.10.31 resolves historical trade evidence on demand from compatible global
observations and approved pre-event provider evidence. Provider results may remain
disposable; evidence is preserved only through one explicit sparse-global policy.
No league-specific historical market warehouse is introduced, unavailable assets
remain unavailable rather than zero-valued, and current Asset Market values remain
strictly fresh-provider-driven.

## Previous release: v1.10.30 - FOIS TradeFact occurred_at Integration Correction

DTOS v1.10.30 completes the v1.10.29 FOIS integration by making the immutable
`TradeFact` contract accept and retain canonical historical event time plus its
existing transaction-time evidence summary. Missing timestamps remain explicitly
unavailable, and current value is never substituted for historical proof.

## Previous release: v1.10.29 - Canonical Historical Trade-Time Intelligence

DTOS v1.10.29 restores the provider-backed occurrence time that Sleeper already
supplies for historical trades, waivers, adds, and drops. Canonical trades and
their asset events now share an offset-aware UTC timestamp without changing
their stable identities.

Historical trade dossiers use only existing Global Sparse Market observations
at or before execution. They report partial or unavailable evidence honestly,
never substitute later or current values, and keep process assessment separate
from outcome. FOIS and Front Office receive the complete canonical trade sample
without restoring the retired HistoricalStore.

---

# DTOS v1.10.26 - Sleeper Season Cache Chain Restoration

DTOS v1.10.26 durably records the full Sleeper dynasty chain before hydrating
individual completed-season caches. A missing or failed season is now explicit
and recoverable instead of silently shortening every history consumer's scope.

Completed seasons hydrate independently, the active season remains honestly
pending, and startup reports partial or failed cache work truthfully. FOIS
scoring is unchanged, canonical history never falls back to HistoricalStore,
and the preserved legacy database is neither opened nor modified.

---

# DTOS v1.10.25 - FOIS Canonical History Null-Placement Correction

DTOS v1.10.25 makes the canonical FOIS history adapter explicitly nullable for final placement. Current or partial Sleeper seasons may publish playoff bracket placeholders before winner and runner-up identities exist; those values now remain unavailable rather than being coerced or invented.

Completed seasons retain their existing FOIS scoring semantics. Missing placement affects evidence completeness only, while trade, draft, waiver, and permanent checkpoint evidence remain usable. The proven zero-read/zero-write HistoricalStore architecture and physical legacy database are unchanged.

---

# DTOS v1.10.24 - Legacy Access Observability Route Correction

DTOS v1.10.24 makes the existing bounded `POST /api/leagues/resources/measure` endpoint reachable in production by narrowing league-context path recognition to the actual league runtime route. It does not change HistoricalStore migration behavior or physically modify the preserved legacy database.

The release retains strict league-ID validation, the existing resource measurement contract, and the fail-closed legacy access guard used to prove zero canonical reads and writes.

---

# DTOS v1.10.23 - HistoricalStore Consumer & Writer Migration

DTOS now sources reconstructible league history from normalized Sleeper season
caches, sources permanent DTOS intelligence from sparse IntelligenceCheckpoint
records, and keeps current identities and relevant-player state in bounded
operational caches. A new compact metadata database retains system-owned cache
checkpoint and synchronization state without copying provider history.

The legacy HistoricalStore remains physically intact but is dormant. Canonical
startup, synchronization, history, FOIS, Front Office, Team HQ, dossiers, Brain,
Asset Market, inspection, and API paths no longer initialize, read, or write it.
Shadow-forbidden diagnostics expose any attempted regression. Physical deletion
and disk reclamation are explicitly deferred to v1.10.24.

## Previous release

# DTOS v1.10.22 - Resource Admission & Heavy-Work Coordination

DTOS now distinguishes verified reclaimable Linux file cache from live memory
pressure during Asset Market admission. The existing 500 MiB reserve, 1.5 GiB
effective ceiling, OOM-event rejection, and 2 GiB runtime limit remain unchanged.

One canonical heavy-work coordinator now gives an unavailable Asset Market first
priority over optional Chromium and DINS capture. Visual work remains pending and
starts after the market generation reaches a safe terminal state.

## Previous release

# DTOS v1.10.21 - Sleeper Canonical Projection Mirror

Sleeper is now DTOS's canonical weekly fantasy projection provider. DTOS scores
Sleeper projected football statistics using each league's actual scoring profile
and never fabricates positional fallback points when provider evidence is
missing. Legitimate zero projections remain distinct from unavailable evidence.

The former DTOS weekly forecast remains legacy/research-only and has zero
canonical production consumers.

## Previous release

# DTOS v1.10.20 - Intelligence Checkpoint Runtime Integration

DTOS now invokes its permanent intelligence-memory service from the canonical
Sleeper synchronization boundary. Newly observed trades, waiver adds, drops,
fantasy draft selections, and deterministic season benchmarks are captured once
with event-time provenance and unavailable evidence represented honestly.
Repeated synchronization is idempotent and ordinary read routes remain free of
checkpoint writes. NFL event triggers without a reliable canonical source remain
explicitly unconnected.

## Previous release

# DTOS v1.10.19 - Sleeper-Backed League Memory & Permanent Intelligence Checkpoints

Sleeper and external providers are now formally the source of reconstructible
facts; DTOS keeps those facts only as disposable caches. League history begins
at the actual provider-discovered Year 1 rather than a DTOS calendar cutoff.
Missing provider history is explicitly partial or unavailable and is never
fabricated or secretly filled from legacy Historical Memory.

DTOS now has a compact permanent intelligence checkpoint contract for meaningful
trade, waiver, draft, NFL-event, and scheduled observations. Checkpoints preserve
execution-time knowledge, source/model provenance, temporal confidence, and pick
lineage without daily full-universe logging or hindsight rewrites. Fresh provider
evidence remains mandatory for current Market Value. Existing Historical Memory
remains untouched and reversible.

## DTOS v1.10.18 - Multi-League Resource Observability & Storage Hygiene

DTOS v1.10.18 makes every significant Asset Market memory-admission decision
durably diagnosable without changing the admission contract. The bounded journal
records explicit decision reasons, cgroup working-set inputs, OOM deltas, browser
process counts, and sanitized lifecycle context across restart and runtime
eviction.

An explicit diagnostic operation now attributes approximate retained memory to
league runtime components without adding profiling work to normal requests.
Asset Market publication also retains exactly one manifest-selected current
artifact per league and safely removes complete stale generations only after
atomic publication. Resource health reports artifact and durable-disk pressure
with documented 20% warning and 10% critical free-space thresholds.

## Previous release

# DTOS v1.10.17 - Multi-League Consumer Integration

DTOS v1.10.17 completes the product boundary introduced by the bounded runtime
manager. An explicit league request now resolves one request-scoped canonical
context and routes crawl, projections, Brain inputs, Asset Market, FOIS,
historical reads, audits, and inspection through that exact runtime.

Secondary league history remains honestly unavailable until its own dynasty
chain is imported, and private secondary runtimes never trigger or expose Live
Visual captures. Default routes retain the configured league contract, while
concurrent A/B requests no longer depend on mutable process-global selection.

## Previous release

# DTOS v1.10.16 - Multi-League Runtime Foundation

DTOS v1.10.16 introduces a lazy league-scoped runtime boundary while preserving
the configured Day Traders league as the default. Runtime state, synchronization,
projection context, Asset Market residency, and diagnostics now have explicit
league identities rather than relying on a last-request-wins singleton contract.

The manager retains at most two warm leagues by default, hydrates a league only
when requested, collapses concurrent hydration, evicts inactive runtimes by LRU,
and releases league-scoped background and market resources. Secondary-league
import is deliberately feature-gated until enabled by deployment configuration.

Durable Historical Memory remains one normalized league-indexed database. Asset
Market artifacts and Live Inspection/Visual evidence are namespaced by league,
while full release DINS remains limited to the designated validation league.

## Previous release

# DTOS v1.10.15 — Projection Snapshot Upgrade Compatibility

DTOS v1.10.15 ensures a durable Forward Production snapshot is reused only when
its schema, model, contract, and semantic policy match the running application.
Incompatible or corrupt snapshots remain durable for diagnostics but are not
published as current intelligence. Cached canonical and Sleeper inputs produce
exactly one compatible replacement without a provider request.

Projection health now reports the running application contract separately from
the actual active and restored snapshot identities, including explicit restore,
upgrade-generation, failure, and durable-publication counters.

## Previous release

# DTOS v1.10.14 — Player-Specific Projection Calibration

DTOS v1.10.14 makes Forward Production genuinely player-specific. The model keeps
its independent raw forecast, then calibrates it using evidence strength, current
role, availability, recent production, and the cached Sleeper projection feed.
Sleeper remains external evidence rather than copied truth; strong DTOS evidence
can still support a documented disagreement.

Projection APIs and audits now expose raw and calibrated DTOS values, adjustment,
reason, confidence, fallback state, evidence depth, zero-versus-missing semantics,
and large-disagreement diagnostics. The calibrated value flows once through the
canonical Brain while Market Value, Historical Memory, FOIS history, Asset Market
lifecycle, and request-time provider boundaries remain unchanged.

## Previous release

# DTOS v1.10.13 — External Mirror Matchup Surface Classification Correction

DTOS v1.10.13 corrects the external mirror's matchup-surface classifier. One
shared strict parser now recognizes only `matchups-<numeric-id>` as a matchup
detail. The public `matchups-page` directory remains mirrorable without being
subjected to detail-only 22-starter validation.

Individual matchup validation remains unchanged and strict: two teams, 22
starters, visible Sleeper and DTOS projections, and semantic/audit reconciliation.
The mirror manifest also exposes deterministic directory-to-detail traversal for
GitHub-only inspection.

## Previous release

# DTOS v1.10.12 — Permanent External Visual Mirror

DTOS v1.10.12 permanently publishes the verified Live Product and Live Visual
Inspection state as a compact GitHub release mirror. External assistants can start
from one stable manifest, download individual current-page PNGs and semantic JSON,
and reconcile matchup projections without rendering the Render origin or downloading
the full DINS archive.

The mirror copies exact verified captures, validates PNG dimensions and SHA-256,
reconciles all matchup starters against semantic inspection and the projection audit,
and sanitizes every public JSON artifact. Core public pages inherit capture and
mirror eligibility from canonical route registration; entity-heavy pages remain
bounded representative/on-demand surfaces. Release-triggered and hourly automation
waits for matching production, Live Visual, and DINS completion before publishing.

GitHub remains inspection-only. DTOS performs no request-time GitHub calls for the
mirror, and mirror availability cannot affect canonical runtime health.

# DTOS v1.10.11 — Live Visual Inspection

DTOS now exposes current rendered product screenshots through the permanent
`/api/inspect/live/visual` contract. Every current matchup is captured at mobile
and desktop viewports from its real public route, validated against canonical
Sleeper and DTOS projections, and served anonymously as a durable PNG.

Capture work is asynchronous, single-flight, fingerprint-deduplicated, and
preserves the previous valid image after failure. Ordinary inspection requests
never launch a browser or mutate canonical application state.

See `docs/LIVE_VISUAL_INSPECTION.md` for discovery, freshness, and future-release
requirements.

## Previous release

# DTOS v1.10.10 — Universal Live Product Inspection & Matchup Projection Presentation

DTOS now has one permanent current-production inspection entry point:
`/api/inspect/live`. Public GET routes register automatically through the
canonical application router, while dynamic collections provide bounded links
for teams, matchups, relevant players, picks, seasons, FOIS, and APIs. Approved
machine/internal exclusions are explicit, and the inspection observer does not
refresh or regenerate canonical DTOS state.

Matchup starter cards now display exact Sleeper and DTOS projections alongside
actual points, with explicit unavailable states and visible partial-coverage team
totals. Semantic matchup inspection exposes displayed and canonical values for
permanent reconciliation checks.

See `docs/LIVE_PRODUCT_INSPECTION.md` for the traversal and developer contract.

## Previous release

# DTOS v1.10.9 — Projection Intelligence Audit Export

DTOS v1.10.9 adds one trustworthy, read-only view of the projection and
intelligence numbers already used by the application. The JSON export at
`/api/audit/projections/current` and its player-oriented CSV companion expose
current matchup starters, projection differences, team reconciliation,
valuation layers, FOIS context, provider diagnostics, and canonical snapshot
identities without triggering synchronization or recalculation.

See `docs/PROJECTION_INTELLIGENCE_AUDIT.md` for the contract and audit-only
difference thresholds.

## Previous release

# DTOS v1.10.7 — Freshness Semantic Threshold Correction

DTOS v1.10.7 makes evidence age semantically stepwise. Exact age remains
observable, but Brain output changes only at documented evidence-family quality
boundaries. Same-tier provider refreshes now retain the canonical Brain and
compatible Asset Market generation; meaningful threshold crossings still
propagate exactly once.

The policy distinguishes time-sensitive projections, slower dynasty-market
evidence, league transaction evidence, performance data, and immutable
historical facts. It is versioned as freshness policy 2.0.

## Previous release

DTOS v1.10.6 introduced bounded Brain input manifests and early semantic
candidate comparison.

DTOS now distinguishes raw provider-observation age from the derived Brain
opinion. A periodic refresh that advances `freshness_age_hours` without changing
confidence, reliability, evidence weight, score, rank, or valuation retains the
published Brain and compatible Asset Market generation. Once staleness becomes
material to those derived outputs, normal semantic publication still occurs.

Compact input-family fingerprints and bounded changed-asset diagnostics make
future semantic differences attributable without exposing raw datasets.

## Previous release

# DTOS v1.10.5 — Projection Semantic Compatibility Correction

DTOS now treats semantically identical restored and freshly observed projection
state as one canonical generation. Nested observation timestamps, transport
latency, request counters, and restore metadata no longer invalidate the Brain or
its durable Asset Market artifact. Stable values, confidence, evidence,
ownership, ordering, and provider dependencies remain strict semantic inputs.

Equivalent background refreshes retain the existing Brain report and market
generation; material projection or valuation changes still publish exactly once.
Projection, Brain, and Asset Market health expose compact semantic diagnostics
and explicit change/no-change counters.

## Previous release

# DTOS v1.10.4 — Durable Projection & Asset Market Restoration

DTOS restores the last valid Projection Intelligence snapshot and compatible
Asset Market artifact from durable storage before background refresh. Original
freshness timestamps and semantic identities survive restart, while bounded
manifests and recovery preserve atomic publication.

## Previous release

# DTOS v1.10.3 — Sleeper Projection Provider Redirect Correction

DTOS now safely follows the single relative redirect used by Sleeper's optional,
undocumented projection service. The policy is scoped only to this provider,
permits at most three HTTPS redirects to allowlisted Sleeper API hosts, rejects
loops, missing locations, insecure downgrades, and host escape, and exposes only
sanitized transport diagnostics.

The projection parser, scoring conversion, consensus model, Brain, valuation,
FOIS, Matchups, historical contracts, and shared HTTP client are unchanged.

## Previous release

# DTOS v1.10.2 — Sleeper Projection Sync & System-Wide Forward Intelligence

DTOS now treats Sleeper's undocumented bulk weekly projection service as optional
external evidence. Background synchronization retrieves one bounded weekly data
set, validates its schema and identities, converts projected statistics with the
league's scoring rules, fingerprints semantic content, and persists immutable
last-valid evidence. Feed failure never blocks readiness or erases DTOS's own
Forward Production model.

Player and matchup contracts distinguish **Sleeper Projection**, **DTOS
Projection**, and the bounded **DTOS Consensus Projection**. Source-pure team
totals disclose starter coverage; the canonical Brain continues to consume one
Projection Intelligence snapshot. Identical feed content causes no downstream
regeneration.

The Sleeper projection interface is undocumented and may change or disappear.
DTOS therefore classifies it as “Sleeper Unofficial Projection Feed — Optional
External Evidence,” provides a kill switch, retains stale evidence safely, and
continues independently when it is unavailable.

## Previous release

# DTOS v1.10.1 — Projection Generation Production-Shape Correction

DTOS now accepts the canonical production player mapping as well as sequence
fixtures when generating Forward Production. Mapping keys safely supply missing
player IDs, conflicting identities fail closed, roster duplicates are collapsed,
and projection health exposes sanitized failure and recovery state.

No projection formula, valuation weight, provider attribution, or matchup logic
changed. Sleeper remains the canonical league/roster/matchup source, while
projections remain attributed to the DTOS Forward Production Model.

## Previous release

### DTOS v1.10.0 — Live Projection Intelligence & Forward Production Engine

DTOS now persists a canonical Forward Production snapshot and reuses it across
Brain decisions, player valuation profiles, and Matchups. Projection evidence is
league-scoring aware, immutable, freshness-labelled, and failure-isolated.

Sleeper's documented public API does not expose an approved projection feed.
Sleeper therefore remains DTOS's canonical league, roster, matchup, identity,
transaction, draft, and NFL-state source. Projections are explicitly attributed
to the DTOS Forward Production Model; they are never called Sleeper projections.

Read-only endpoints are available at `/api/projections`, `/api/projections/health`,
`/api/projections/providers`, `/api/projections/players/{player_id}`, and
`/api/projections/weeks/{week}`. No endpoint performs external provider work.

## Previous release

### DTOS v1.9.6 — Historical Player Leaders Query Optimization

DTOS v1.9.6 removes the final cold History bottleneck by using a measured
season-scoped player aggregation index and one bounded canonical identity query.
Historical totals, names, positions, ordering, presentation, progress, FOIS,
valuation, and Asset Market behavior remain unchanged.

## Previous release

# DTOS v1.9.5 — History Read-Path Performance

DTOS v1.9.5 makes season History pages responsive by building only the requested
section, offloading database-backed read-model work from the event loop, and
aggregating player leaders in a bounded SQL query. It preserves the v1.9.4
historical evidence, schemas, ordering, provenance, canonical `5/6` progress,
valuation behavior, and FOIS model unchanged.

## Previous release

# DTOS v1.9.4 — Valuation, FOIS & League History Corrections

DTOS v1.9.4 completes independent intrinsic, contender, and rebuilder valuation
layers for supported active assets, corrects the FOIS centered-score calibration
without conflating score and confidence, and adds provider-free year-level league
archives backed by immutable Historical Memory. Unsupported layers retain honest
evidence limitations, prior FOIS snapshots retain their model versions, and the
active 2026 season remains explicitly current rather than final.

## Previous release

# DTOS v1.9.3 — Asset Market Restart Lifecycle Correction

DTOS now deterministically schedules one background Asset Market build when startup or restart finishes without a compatible durable artifact. The correction closes an orchestration hole where the market could become eligible while remaining model-less and idle. It does not change valuation, Historical Memory, FOIS, or v1.9.2 presentation behavior.

## Previous release

### v1.9.2 — Intelligence Presentation & Data Utilization

DTOS now turns more existing Brain, FOIS, Asset Market, and Historical Memory evidence into readable product guidance. Human-facing pages lead with names, ranks, values, confidence, availability, and outcomes; technical provenance remains accessible without replacing the decision meaning. This release does not add an intelligence engine or change canonical valuation behavior.

## Previous release

### v1.9.1 — FOIS Presentation Contract Correction

DTOS v1.9.1 completes the public presentation contract for the Front Office Intelligence System introduced in v1.9.0. The `/fois` page now uses the shared DTOS page header, selects the active loaded league when no query parameter is supplied, presents persisted executive profiles, and provides a functional GM Rankings action.

The release does not change FOIS scores, evidence, model outputs, persistence, startup scheduling, Historical Memory, or Asset Market behavior. Explicit unavailable leagues and genuinely missing or pending FOIS data remain honest, distinct states.

## Validation focus

- Shared page-header and primary-action contracts at desktop, tablet, and mobile.
- Canonical loaded-league selection and explicit valid-league override.
- Ten persisted production GM profiles visible without a league query parameter.
- FOIS output equivalence and v1.9.0 startup-correction preservation.

## Previous release

# DTOS v1.9.0 — FOIS General Manager Intelligence System

DTOS now evaluates the executive responsible for a franchise during a specific
tenure—not merely the current team. FOIS separates results, decision process,
context, and recovery; keeps GM quality distinct from current team quality; and
uses the canonical Brain, Competitive Window, Asset Universe, Relevant Player
Universe, and immutable Historical Memory as evidence sources.

Versioned tenure identities and takeover snapshots prevent new owners from
inheriting prior-owner decisions or scores. Full-history evaluation has no hard
ten-year cap. Trading, roster construction, drafting, Results, confidence,
completeness, evidence provenance, Executive Profiles, resumes, comparisons, and
franchise GM history are available through persisted read-only FOIS contracts.
Missing evidence remains visibly unavailable rather than becoming a failing grade.

## Previous release: v1.8.15

# DTOS v1.8.15 - Relevant Player Universe

DTOS now retains active model state only for players relevant to imported league history, current ownership, or the top 150 available canonical free agents. Every retained player carries explicit reason codes, while retired and former players required by immutable evidence remain directly discoverable. The durable migration derives membership from existing history without replaying providers or changing historical events, checkpoints, provenance, or the canonical 5/6 progress contract.

## Previous release: v1.8.14

# DTOS v1.8.14 - Deterministic Asset Market Restart Lifecycle

DTOS v1.8.14 makes Asset Market restart behavior a single deterministic lifecycle. The application now completes one canonical startup epoch before it evaluates durable market artifacts or permits market construction. A compatible artifact loads once without reconstruction; incompatible, corrupt, incomplete, and missing candidates retain distinct diagnostics.

The release also prevents request freshness and delayed deployment maintenance from creating duplicate startup-adjacent synchronizations. Normal periodic refresh begins after the startup epoch and continues to publish exactly one safe replacement when semantic market inputs genuinely change. Existing memory, backoff, historical `5/6`, dataset-scope, provider-free read, and output contracts are unchanged.

## Previous release: v1.8.13

DTOS v1.8.13 closes the production-scale retained-memory gap exposed when historical coverage and Asset Market reads run against the complete durable database shape. The release adds bounded combined-read diagnostics and preserves every existing output, historical record, memory ceiling, reserve, and provider-free read contract.

---

# DTOS v1.8.12 — Cgroup-Aware Market Memory Admission

DTOS v1.8.12 corrects Asset Market memory admission under Linux cgroup v2. It subtracts only validated reclaimable `inactive_file` cache from `memory.current`, retains all existing hard limits and reserves, and fails conservatively when metrics are unavailable or inconsistent. Generation-aware backoff prevents repeated polling from launching identical rejected builds while preserving safe retries after time, input changes, or meaningful memory improvement.

The release does not change market calculations, historical data, infrastructure, or public product output.

---

# DTOS v1.8.11 — Retained Asset Market Summary Contract

DTOS v1.8.11 makes `/api/market` a bounded metadata-only summary that returns retained lifecycle, availability, generation, provenance, historical progress, and subresource links without constructing or loading an Asset Market model. It remains HTTP 200 during cold startup, warming, replacement, and safely failed replacement states.

Directory routes keep their established bounded-warming behavior. Search and detail remain `live_store`; retained directory, health, and artifact metadata remain `artifact_build`. No provider, SQLite, artifact, digest, or historical work was added to the summary route.

---

# DTOS v1.8.10 — Asset Market Health Dataset Scope

DTOS v1.8.10 completes the Asset Market historical provenance contract by exposing `historical_dataset_version_scope: artifact_build` wherever market health exposes a retained artifact dataset version. The version and scope are published atomically with the active model and remain consistent through compatible restart loading, non-semantic reuse, replacement warming, and failed publication.

Search and asset-detail responses continue to expose current `live_store` history. Directory and retained-artifact responses remain `artifact_build`. This correction adds no request-thread database work, provider synchronization, archive scanning, semantic invalidation, or market-output changes.

---

# DTOS v1.8.6 — Asynchronous Market Generation

DTOS v1.8.6 removes archive-wide durable-generation preparation from cold Asset Market request execution. The first request now claims one process-local background worker using retained in-memory lifecycle state and immediately returns the canonical retryable warming response.

The worker performs database UUID lookup, historical dataset calculation, identity archive aggregation, cache-key resolution, compatible-artifact loading, bounded construction, and atomic publication away from the event loop. Market health reports the current preparation phase, refresh state, duration, served generation, and failures without hydrating product state.

Compatible last-valid generations continue serving while a replacement is prepared. Incompatible store instances warm safely. Completed generations preserve existing rankings, ordering, Brain snapshots, valuation layers, historical provenance, serialization, and provider-free read behavior.

No infrastructure, storage, compute plan, pricing, database schema, valuation formula, ranking, or historical evidence changed.

---

# DTOS v1.8.4 — Bounded Asset Market Construction

DTOS v1.8.4 removes the production OOM path in the first cold Asset Market request. Profiling found four simultaneous universe-wide representations: full canonical valuation envelopes, compact summaries, an ID dictionary, and duplicated normalized search strings. The old builder retained roughly 260 MB locally and exceeded the 2 GB Render cgroup when added to the synchronized production baseline.

The market now streams canonical assets directly into an atomic, versioned SQLite read model on the existing durable storage. Directory filtering, ordering, and pagination run in SQL before JSON hydration; search uses the indexed compact representation; expanded dossiers hydrate only the selected canonical asset and its history. Compatible generations survive process restarts without rebuilding.

Cold requests start one bounded background build and receive an explicit retryable warming response. A cgroup-aware guard checks available construction budget before and between stages and defers safely rather than risking worker termination. Market health remains metadata-only.

No market formulas, public schemas, ordering, Brain snapshots, valuation layers, historical evidence, provider behavior, infrastructure, or pricing changed.

---

# DTOS v1.8.3 — Production Memory Lifecycle

DTOS v1.8.3 coordinates its largest in-process memory phases instead of allowing their peaks to overlap. Initial Sleeper synchronization and cache persistence finish before historical backfill begins, and cold Asset Market construction is deferred while synchronization, valuation, persistence, or historical work is active.

`/api/market/health` is now a metadata-only readiness surface. It reports retained generation, count, build, cache, lifecycle, and bounded memory information without constructing a market model or triggering providers, Brain evaluation, historical hydration, or synchronization. Ordinary warm reads remain lock-light, and a last-valid market remains available during unsafe rebuild windows.

Cache persistence now incrementally encodes JSON to a same-directory temporary file, flushes and synchronizes it, and atomically replaces the prior cache only after success. Failed writes retain the previous valid cache and remove temporary artifacts.

The lifecycle coordinator records bounded process RSS, virtual memory, system availability, and Linux cgroup current/limit values at phase boundaries. It never publishes host paths, database identities, secrets, or raw payloads.

No Asset Market formulas, rankings, canonical Brain snapshots, historical outputs, provider behavior, infrastructure, or pricing changed in this release.

# DTOS v1.8.2 — Asset Market Query Performance

DTOS v1.8.2 removes repeated aggregate database work from warm Asset Market reads. HistoricalStore now computes each league's canonical dataset identity once under concurrency and invalidates it only after a successful committed evidence, identity, quality, migration, or repair change. Durable database UUIDs continue detecting same-path database replacement without exposing private storage details.

Asset Market search retains normalized compact documents at model construction. Current players, structured filters, empty searches, future picks, free agents, and no-result queries remain inside the compact index; retained historical aliases provide former-player discovery without constructing full dossiers or recommendations.

Historical Graph player dossiers now use a bounded dataset-versioned LRU with single-flight first construction. Repeated expansion preserves byte-equivalent canonical history, Brain identity, recommendation provenance, and API contracts while avoiding repeated ownership, season-summary, and positional preparation.

---

# DTOS v1.8.1 — Asset Market Cache Stability

DTOS v1.8.1 corrects the production performance blocker discovered after v1.8.0. Instrumentation proved that ongoing enrichment changed the logical Historical Memory dataset version on every commit, causing the compact 12,331-asset market model to rebuild repeatedly even though those writes did not change its directory summaries.

HistoricalStore now owns a private random database UUID persisted inside SQLite. It remains stable across reads, writes, WAL checkpoints, vacuum-compatible maintenance, and controlled restarts, while a recreated database receives a new identity. The process cache additionally retains store-instance isolation and never exposes paths or the private UUID.

Compact market invalidation now follows only inputs that can change compact output. Historical search, detail dossiers, and response metadata continue to consume the independently versioned durable Historical Asset Graph. Current-asset searches skip historical discovery once the requested page is already satisfied.

---

# DTOS v1.8.0 — Asset Market & Dynasty Exchange

DTOS v1.8.0 introduces the Asset Market as the application’s primary destination. Players, free agents, retired players present in durable history, rookies, taxi assets, and owned draft picks are discoverable through one deterministic market contract. The Commissioner Desk remains available at `/commissioner`.

The market preserves distinct market, intrinsic, league-adjusted, contender, and rebuilder layers. It consumes existing Valuation Universe and Brain contracts instead of recalculating intelligence in routes. Missing evidence remains unavailable and is never silently replaced. Canonical Brain recommendations expose confidence, snapshot identity, evidence, and reasoning.

The read model is versioned, bounded, single-flight, and provider-sync-free. Directory pagination occurs before historical dossier hydration; player and pick history is loaded only for selected assets. Market health and DINS inspection expose dataset identity, cache state, build timing, duplicate identity checks, and read-path guarantees.

---

# DTOS v1.7.14 — Canonical Trade History Discovery

DTOS v1.7.14 makes Historical Trade Dossier discovery use the same durable Historical Memory dataset and completed-status contract as its detail routes. DINS no longer advertises current cached Sleeper transactions as historical dossiers when canonical historical evidence is absent.

Current-only transactions remain available through current Transactions and Trade surfaces. Inspection discovery records a deterministic `canonical_historical_trade_unavailable` exclusion with the durable dataset version, rather than fabricating a dossier or capturing a known 404 route.

Discovery remains read-only, bounded, deterministic, and provider-sync-free.

---

# DTOS v1.7.13 — Canonical History Progress Presentation

DTOS v1.7.13 makes the durable player-week enrichment progress contract the single presentation source for History, coverage, inspection, and DINS. Exact counters and season states remain primary; rounded percentages are secondary.

The History page now distinguishes foundation import completion from player-week enrichment. A current-season `completed_with_pending` state is presented honestly as terminal and ready with expected evidence pending, without marking the active season complete or mutating historical state.

Migration version 5 safely repairs inconsistent persisted job metadata, including the v1.7.11 `78/6` state, and records the prior value, repaired value, derivation, and season classification. The repair is idempotent and does not modify immutable evidence, record keys, provenance, leases, or batch rows.

Import diagnostics now expose completed, pending, and failed seasons with an explicit consistency flag. Foundation imports retain their established category-level progress semantics.

---

# DTOS v1.7.11 — Historical Enrichment Batch Persistence

DTOS v1.7.11 makes historical player enrichment durable and efficient on the persistent Render volume. Nflverse weekly data is consumed as bounded batches, while each batch atomically persists raw evidence, derived fantasy scoring, durable progress, and lease renewal.

Importer identity remains at version 1.2. Existing v1.7.10 record keys therefore remain canonical, completed work can be replayed safely, and logically duplicate evidence is ignored instead of rewritten.

The new migration adds durable batch-progress records without changing historical API schemas, canonical identities, provider provenance, scoring outputs, or immutable historical evidence.

---

# DTOS v1.7.10 — Durable Historical Storage

DTOS v1.7.10 makes Historical League Memory restart-safe on a single Render instance. Production now requires an explicitly mounted and writable durable-storage root; the historical database must resolve beneath that root, and startup readiness fails with a clear reason instead of creating an ephemeral substitute.

The SQLite database remains the canonical durable home for immutable records, import jobs, checkpoints, leases, heartbeats, data-quality issues, reconciliation evidence, and dataset-version inputs. First-time initialization is built beside the target and atomically installed without replacing an existing database. WAL journaling, full synchronous durability, foreign keys, and a bounded busy timeout support the single-instance deployment contract.

Historical graphs remain bounded process-local objects to avoid persisting large hydrated payloads. A small, atomic read-model manifest on the durable disk records the cache identity, dataset version, schema version, and successful generation timestamp so restarts retain deterministic rebuild provenance. Temporary Sleeper caches, provider payloads, source files, and logs remain outside the persistent disk.

---

# DTOS v1.7.9 — Historical Import Memory Stability

DTOS v1.7.9 corrects the confirmed Render OOM mechanism without changing historical contracts. Coverage statistics are calculated directly from indexed SQLite records, asset details hydrate only their relevant source rows, and global graph hydration is blocked while an import owns the write lease.

The importer fetches and persists one week at a time instead of retaining a season of raw Sleeper responses. Production-scale concurrency validation uses the retained 200 MB historical database and enforces a hard 450 MiB RSS ceiling with a target below 400 MiB.

Historical outputs, ordering, provenance, unresolved identities, leases, checkpoints, and provider-free read behavior remain unchanged.

---

## Previous release: v1.7.8 — Historical Import & Read-Model Lifecycle Stability

DTOS v1.7.8 stabilizes the production lifecycle discovered during v1.7.7 verification. Historical graph objects now start lightweight and construct only the route-specific indexes needed by asset, player, or coverage reads. Player directories use indexed identities without loading every weekly payload, player dossiers load only the requested player's weekly records, and coverage counts are aggregated directly in SQLite.

The process retains one immutable graph generation instead of two. Production-scale validation measures the entire cold-to-warm read workflow and confirms identical historical outputs without provider synchronization.

Historical import recovery now waits for a live worker heartbeat, detects bounded lease expiration, removes the stale lock atomically, requeues the interrupted job visibly, and continues from completed checkpoints with a single importer.

---

## Previous release: v1.7.7 — Historical Asset Graph Read-Path Optimization

DTOS v1.7.7 corrects the production read-path timeout discovered after v1.7.6 without changing historical outputs or synchronization behavior. A dataset-keyed read model now builds the normalized graph once per immutable history/current-identity version and reuses deterministic indexes across every historical consumer.

The cache key includes league identity, historical dataset hash, historical schema, importer, graph, player-history/calculation, read-model, and current verified identity metadata. Concurrent first reads are single-flight, only complete models are published, a failed rebuild retains the prior valid model with an explicit stale diagnostic, and process memory is bounded to two dataset versions.

Directory pagination occurs before dossier hydration. Player detail reads use asset, parent-transaction, player-week, season-total, trade, and pick-conversion indexes rather than reconstructing unrelated assets. Historical reads remain provider-free and never initiate Sleeper synchronization.

Diagnostics expose build/load/query durations, build count, hits/misses, dataset version, asset/event counts, hydrated-record count, last successful build/error, and approximate model size through historical coverage and directory contracts.

---

## Previous release: v1.7.6 — Historical Asset Graph & Connected Dossiers

DTOS v1.7.6 makes verified Day Traders history a connected application contract instead of an isolated report. The new Historical Asset Graph supplies stable player, pick, transaction, trade, event, and franchise identities to dossier pages, search, historical APIs, Team Headquarters, Front Office Intelligence, and the canonical Brain.

Historical ingestion now archives traded-pick snapshots and attaches source league, season, record identity, retrieval time, schema/importer versions, source hashes, provenance, and availability to normalized payloads. Completed movements can produce ownership intervals; failed and pending movements remain visible evidence but cannot change ownership.

Player season summaries retain the matching season's scoring-settings version and distinguish missing observations from zero. The active 2026 season is explicitly in progress. Historical value-at-event remains unavailable unless DTOS has a timestamped valuation snapshot; current values are never silently backdated.

New contracts include `/api/history/assets`, asset event and ownership endpoints, player historical endpoints, `/api/picks/{pick_id}`, historical Trade Dossiers, franchise history, coverage reporting, and unified `/api/search`. HTML Pick and Trade Dossiers provide corresponding connected navigation.

Known honest limitations:

- Sleeper matchup history supplies league-scored points but not lossless raw NFL stat components or historical advanced usage.
- Historical matchup payloads do not distinguish taxi and reserve assignments; those states remain explicitly unavailable unless independently sourced.
- Older or retired Sleeper IDs without verified metadata remain searchable as unresolved IDs and are never assigned guessed names.
- Value at trade remains unavailable without a contemporaneous valuation observation.

---

## Previous release: v1.7.5 — League Payload Memory Safety

This corrective release keeps `/api/league` focused on league data and a compact Brain summary. Full canonical asset intelligence and timelines remain available through `/api/brain`. The change prevents a 35 MB compatibility response from materializing the full Brain and its duplicated timeline during every request, eliminating the production memory-pressure path observed during v1.7.4 verification.

---

# DTOS v1.7.4 — Brain Integration & Unified Decision Engine

DTOS now has one public Brain boundary. Every major intelligence consumer receives the same cached asset values, evidence scores, explanations, and histories through the Intelligence Orchestrator. The release adds a distinct, explainable Decision Confidence metric, a Brain dashboard, migration diagnostics, health APIs, and DINS coverage. Existing valuation contracts remain compatible; provider calls and valuation recalculation remain outside request rendering.

## Canonical endpoints

- `/brain`
- `/api/brain`
- `/api/brain/health`
- `/api/brain/migration`
- `/api/brain/assets/{asset_id}`
- `/api/brain/timeline/{asset_id}`

---

# DTOS v1.7.3 — Valuation Intelligence Engine (DTOS Brain Phase I)

DTOS now reasons over cached multi-source evidence instead of treating provider consensus as an answer. Every canonical player and pick receives separate Coverage, Confidence, and Agreement scores, a provider/category breakdown, five independent valuation layers, a readable explanation, a bounded evidence timeline, and transparent diagnostics.

The engine is generated during background synchronization and performs no external request during page or API handling. Provider reliability, freshness, identity quality, agreement, sample size, and evidence-family lineage determine each contribution. Missing or conflicting evidence lowers confidence explicitly rather than creating false certainty.

New APIs expose evidence, per-asset reports, confidence, coverage, agreement, explanations, timelines, and diagnostics. The valuation dashboard and DINS contract now inspect the same cached intelligence model used by downstream DTOS systems.

## Previous release: v1.7.2

### Multi-Source Market Intelligence Provider Network

DTOS now treats each provider as measured evidence rather than truth. Approved FantasyCalc and DynastyProcess feeds, completed Sleeper trades, league-local behavior, nflverse historical evidence, and the independent DTOS historical model are registered with explicit purpose, lineage, licensing, freshness, coverage, and dynamic reliability. FantasyPros remains credential- and license-gated; KeepTradeCut remains unavailable because no approved integration exists.

Weighted consensus groups correlated sources into evidence families, so a derivative source cannot receive an extra independent vote. Missing, stale, unmatched, ambiguous, conflicting, or restricted evidence lowers confidence and remains visible. Ordinary application requests use a cached read model and never refresh providers. Automatic calibration remains bounded, reversible, model-level only, and now also requires sufficient multi-family coverage and a conflict-free provider network.

## Previous release

### DTOS v1.6.7 — GitHub DINS Artifact Publication Completion

DTOS v1.6.7 closes the inspection-publication gap without adding a paid service or
changing the inspected application commit. Production discovers immutable DINS
ZIP, manifest, and checksum assets directly from the matching public GitHub
Release, validates version/build/commit/schema/capture identity, and reports an
explicit publication state through the inspection API.

Generated browser artifacts remain outside Git history. The post-deployment worker
captures the exact Render commit, packages deterministic sanitized assets, uploads
them to its existing release, and production becomes complete after public identity
and checksum verification.

## Previous release

### DTOS v1.6.6 — Team Headquarters Mobile Overflow Correction

DTOS v1.6.6 is a focused production correction for a responsive defect discovered
during the complete v1.6.5 DINS audit. The Team Headquarters Core Intelligence
grid now collapses within tablet and mobile widths instead of extending beyond the
viewport. No intelligence formulas, provider behavior, or application workflows
changed.

## Previous release

### DTOS v1.6.5 — Product Design System, Navigation & Consistency

DTOS v1.6.5 unifies every major Front Office surface around a shared visual and
interaction language. Pages now state what decision they support, show fresh data
context, and lead to a clear next action. Recommendations use one explainable
contract, league-relative grades state what they mean, and mobile and keyboard
behavior share permanent primitives.

The Commissioner Desk now follows the executive sequence: what changed, what to
do, my team, league opportunities, league context, then the compact snapshot.
Preseason team cards present projections and odds instead of empty standings.

DINS records deployed commit and timestamp provenance and treats missing product
contracts, generic dynamic names, exposed internal identifiers, local artifact
URLs, and critical accessibility regressions as release failures.

No intelligence formulas, provider behavior, or cached-state semantics changed.

## Previous release

### DTOS v1.6.4 — Team Identity Normalization & Team Headquarters Polish

DTOS now presents every franchise by its canonical identity throughout Team Headquarters, Commissioner Desk, intelligence summaries, and DINS. Team Headquarters has a cleaner executive hierarchy with one competitive-window classification and one primary recommendation, while detailed evidence remains available in a collapsed disclosure.

Preseason pages now emphasize projections instead of empty results, unknown bye weeks are omitted, and unfinished controls have been removed. The tracked HTTP release validator permanently rejects rendered generic numbered team and roster fallbacks when canonical league identity is available.

---

# DTOS v1.5.5 — Production Request Latency

The Commissioner Desk now avoids repeated valuation of the same trade package
combinations. Eligible packages are valued once per proposal shape, balance
filtering occurs before guardrail evaluation, and guardrails reuse the same
canonical package values.

For the populated production-scale league fixture, cold homepage model generation
fell from approximately 4.49 seconds to 1.04 seconds locally. Proposal counts,
selection, ordering, and serialized output remain identical to v1.5.4 across all
nine trade partners.

The earlier 18.397-second production matchup observation was transient deployment
contention rather than persistent matchup behavior. Repeated v1.5.4 production
requests measured 2.636–3.003 seconds, consistent with the hosting platform's
slower CPU allocation. Matchup intelligence and caching behavior are unchanged.

---

# DTOS v1.4.5 — League Intelligence & Team Grading

Team strength is now evaluated relative to the selected league. Every franchise receives the same reusable Team Intelligence Card with overall, current, dynasty, lineup, depth, position, draft, youth, future, flexibility, and liquidity grades.

Commissioner Desk, Team Headquarters, Front Office Intelligence, League Intelligence, and public crawl APIs now share the same competitive-window vocabulary and contender totals. Before Week 1, projected order replaces misleading 0–0 standings.

See `docs/TEAM_INTELLIGENCE.md` for weighting, percentile thresholds, API fields, and limitations.

---

# DTOS v1.4.4 — Valuation Calibration and Trade Safety

DTOS now compares all player, pick, market, and package values on one documented 0–1000 scale. FantasyCalc and DynastyProcess retain their raw values but are normalized independently before consensus. Internal DTOS values and draft picks are converted through explicit deterministic methods.

Trade Intelligence now applies package diminishing returns and rejects low-value aggregation that lacks a premium centerpiece, including inappropriate superflex quarterback offers. Calibration state, provider agreement, confidence, and warnings are exposed in player intelligence and public crawl contracts.

Full methodology and current limits are documented in `docs/VALUATION_CALIBRATION.md`.

---

# DTOS v1.4.3 — Public Crawl API

DTOS now exposes the synchronized public league state through fast, cached, read-only JSON endpoints designed for ChatGPT and other standards-compliant crawlers.

## Highlights

- `/api/crawl` publishes version, league, sync, page, endpoint, and cache discovery metadata.
- `/api/crawl/snapshot` consolidates public league, roster, standings, picks, matchup, transaction, Front Office, trade, ranking, recommendation, alert, and sync data.
- Section endpoints provide teams, Front Offices, trades, transactions, matchups, picks, and standings without triggering Sleeper synchronization.
- Crawl artifacts use the shared intelligence cache, are isolated by league and sync generation, and invalidate after successful synchronization.
- Public serialization excludes credentials, environment variables, internal paths, and administrator-only state.
- `robots.txt` and `sitemap.xml` make the public site discoverable while excluding mutation and administrative paths.
- FantasyCalc and DynastyProcess public values now refresh into the canonical market cache with visible attribution.
- Sleeper player metadata, depth-chart fields, ownership, transactions, and trending activity reach player pages end to end.
- Provider failures preserve prior data only as a disclosed cached fallback; unsupported sources state the exact limitation.
- Bijan Robinson resolves to Sleeper ID `9509`; FantasyCalc value `10213` remains a value, never an identity.
- Canonical DTOS player identities reconcile Sleeper, FantasyCalc, KeepTradeCut, FantasyPros, Underdog, and Dynasty Daddy identifiers when supplied.
- Normalization covers names, teams, position eligibility, free agents, rookies, values, rankings, ADP, timestamps, confidence, and metadata.
- Invalid values, broken IDs, provider mismatches, and conflicting metadata are blocked before entering consensus.
- Provider reliability tracks success, failure, schema stability, and latency.
- Consensus 2.1 weights confidence, reliability, freshness, agreement, coverage, and missing sources without using a simple average.
- Sleeper trending adds and drops use the documented public API and remain cached for offline operation.
- Player dossiers display normalized identity, consensus, provider values, freshness, confidence, availability, licensing, and unavailable reasons.
- `/api/players/{player_id}/intelligence` exposes the full normalized player contract.
- Settings provides a Provider Activation Dashboard.

## Metadata

- Version: 1.4.3
- Build: 1430
- Codename: Public Crawl API

## Provider boundaries

- Sleeper league, player, roster, transaction, trade, matchup, metadata, and trending endpoints are active through its official read-only API.
- Cached provider values are normalized and attributed when legitimately supplied to DTOS.
- FantasyCalc remains subject to its attribution, caching, and commercial-use terms.
- Providers without approved public or licensed access remain explicitly disabled; no scraping or fabricated data is introduced.

## Non-goals preserved

No championship probability, Decision Engine change, trade recommendation change, machine learning, or scouting feature was added.

# DTOS v1.5.0 — Historical League Memory & Player Performance Intelligence

DTOS now preserves league and player evidence longitudinally instead of treating synchronized current state as history. A versioned SQLite store retains league-season configuration, franchise identity changes, weekly roster and matchup evidence, standings, playoff brackets, drafts, transactions, trades, player points, values, predictions, and Team Intelligence snapshots with provider provenance.

Historical import is resumable and idempotent. Missing raw NFL statistics and advanced usage are never converted to zero: Sleeper-scored fantasy points are retained as observed evidence, while unsupported components carry explicit availability reasons.

Public historical APIs are paginated and filterable by league, season, week, franchise, and player. Minimal League, Team, and Player History views expose available trends without drawing misleading lines through missing weeks.

See `docs/HISTORICAL_MEMORY.md` for schemas, import behavior, provenance, storage, performance, and current source limitations.

---
# DTOS v1.5.1 — Historical Data Reliability & Player Data Enrichment

Historical imports now persist durable jobs, granular checkpoints, worker leases,
retry classification, and step-based progress. A deployment or provider interruption
can resume without discarding completed categories or blocking ordinary requests.

DTOS also adds a free, attributed nflverse adapter for weekly raw player statistics.
Stable GSIS-to-Sleeper identity mappings are required; ambiguous or unresolved
players are excluded. League-season scoring settings produce separately versioned
fantasy scoring records, with incomplete components and confidence reported.

Advanced snaps, routes, and injury designations remain unavailable unless a future
approved provider supplies them. Missing metrics remain null and never become zero.

---

# DTOS v1.5.2 — Initial Backfill Performance

Fresh deployments now persist each bounded historical batch in one SQLite
transaction. The importer still yields between batches, renews its durable lease,
persists granular checkpoints, and uses immutable record keys for safe replay.

In a production-scale empty-database profile, the 30,051-record backfill fell from
468.162 seconds to 28.673 seconds. Batch persistence fell from 445.074 seconds to
6.987 seconds, while the longest transaction fell from 5.889 seconds to 0.046
seconds. Existing historical and enrichment behavior is unchanged.

---
# DTOS v1.5.6 — Deployment Readiness

DTOS now exposes separate liveness and readiness probes, keeps empty-data
instances out of service until synchronization succeeds, and delays cached
deployment maintenance for 30 seconds so initial user traffic does not compete
with synchronization and historical backfill startup.

Deployment diagnostics are opt-in through `X-DTOS-Diagnostics: 1` and expose
application request timing and process uptime without changing ordinary
responses. Local deployment-transition profiling kept liveness below 3 ms
during a concurrent matchup request and produced cached matchup medians of
approximately 0.58 seconds with graceful process cleanup.

---
# DTOS v1.5.7 — Historical Recovery

The production v1.5.6 foundation import encountered an `httpx.ReadError` while
reading a Sleeper response during 2025 weekly history retrieval. That transport
exception was outside the existing retry classification and stopped the import
after 23,595 records.

DTOS now treats all HTTPX transport failures as bounded retry candidates, logs
the exact Sleeper path and attempt, and preserves the original exception after
four unsuccessful attempts. Recovery skips complete 2021–2024 checkpoints and
replays incomplete 2025 records through the existing immutable record keys.

A fresh real-provider proof produced the canonical 30,051 records in 23.00
seconds. Consecutive reruns added zero rows, with zero duplicate record keys,
duplicate provider identities, or orphaned checkpoints. Seasons 2021–2025 are
complete. The preseason 2026 foundation is present while weekly rosters,
matchups, transactions, trades, and player-week data remain explicitly pending.

---
# DTOS v1.5.8 - Matchup Performance

Matchup market normalization now prepares each provider's value distribution once
per evaluation and reuses it for every player. Percentile ranks use binary-search
counts over the same sorted population, preserving the existing 70% provider-range
and 30% percentile formula exactly.

Production-scale local profiling reduced calls in the matchup fast path from about
2.89 million to 0.77 million. Median direct evaluation fell from approximately
0.84 seconds to 0.44 seconds, and five repeated local HTTP requests completed in
0.41-0.62 seconds. Trade Intelligence and package generation remain excluded from
the matchup route, and no shared matchup cache or historical behavior changed.

See `docs/MATCHUP_PERFORMANCE.md` for the measured pipeline and invariants.

---
# DTOS v1.5.9 - Valuation Calibration

DTOS now distinguishes its independent intrinsic player value from a separate
calibrated value that incorporates normalized public market evidence. Roster
grades, positional tiers, contender and rebuild profiles, and Trade Intelligence
consume that shared result, with confidence and blend weights remaining
explainable.

Draft-pick values now preserve a steeper round curve. A permanent 50-asset golden
test set covers elite players through developmental assets and representative
first- through fourth-round picks to detect future drift.

See `docs/VALUATION_CALIBRATION_V159.md` for methodology and limitations.

---
# DTOS v1.5.10 - Intelligence Quality Audit

DTOS intelligence was audited across all ten franchises, 120 prioritized trade
recommendations, the full player tier range, every supported rookie-pick round,
and competitive-window edge cases.

The audit found that the selected Front Office received calibrated market-backed
player cards while comparison teams received intrinsic-only cards. That made
league ranks and classifications depend on which franchise was selected. All
teams now use one neutral, cached, calibrated comparison contract. Team
Intelligence also consumes the canonical pick evaluator instead of a stale
duplicate round table.

The permanent golden benchmark now contains 82 representative player, pick,
archetype, team-window, and trade-package scenarios. See
`docs/INTELLIGENCE_QUALITY_AUDIT.md` for the league table and remaining limits.

---
# DTOS v1.5.11 — Competitive Window Contract

DTOS now computes each franchise's competitive window exactly once from calibrated
league-relative Team Intelligence. Decision, Front Office, Trade Intelligence,
recommendations, team pages, and APIs consume the same immutable contract.

The contract exposes the classification, confidence, championship/playoff/rebuild
scores, explainable reasons, strengths, weaknesses, generation timestamp, and
contract version. Valuation and Team Intelligence now complete before any trade
or recommendation can use the window, eliminating stale pre-calibration labels.

See `docs/COMPETITIVE_WINDOW_CONTRACT.md` for the dependency flow, consumer
boundaries, serialization behavior, and extension contract.

---
# DTOS v1.6.0 — Front Office Intelligence System Foundation

DTOS now has a parallel foundation for evaluating long-horizon franchise
management without replacing existing roster, valuation, historical,
competitive-window, or intelligence systems.

FOIS defines versioned contracts for scores, categories, metrics, evidence,
confidence, completeness, owner and franchise identity, model configuration, and
future cross-category traits. The initial weights are Results 35%, Trading and
Asset Management 25%, Roster Construction 20%, and Drafting and Talent
Evaluation 20%.

The subsystem is disabled by default with `DTOS_FOIS_ENABLED`. When enabled,
explicit cached facts are evaluated off the event loop and saved idempotently.
Unsupported evidence is disclosed as unavailable or insufficient and never
converted to zero. Advanced metrics remain provisional pending deeper historical
valuation, lineup, transaction, draft, and probability evidence.

See `docs/FOIS_FOUNDATION.md`.

---
# DTOS v1.6.1 — FOIS Results and Competitive Cycle Engine

Results is now the first production-scored FOIS category. DTOS evaluates observed
championships, championship games, Final Fours, playoff appearances, winning
seasons, actual-matchup win rate, league-size-normalized finishes, sustained
excellence, rebuild duration, reload efficiency, contention windows, competitive
longevity, and peak performance.

A reusable `CompetitiveCycleAnalyzer` produces explainable season timelines,
contention and rebuild cycles, peak seasons, reload timing, and full-history,
trailing-ten, trailing-five, trailing-three, and current-cycle windows. Missing
history and ownership changes reduce confidence and completeness without reducing
the outcome score.

The engine reads only immutable cached Historical Memory records. It performs no
provider I/O, runs through the existing worker-thread boundary, and persists its
timeline and cycle detail inside idempotent FOIS snapshots. Trading, Roster
Construction, and Drafting remain unchanged and out of scope.

---
# DTOS v1.6.3 — Complete Visual Inspection & Release Verification System

DINS 2.0 makes DTOS externally auditable as both a semantic product and a rendered web application. Public inspection APIs automatically inventory registered HTML pages, expose lightweight versioned artifact bundles, and report whether the bundle matches the deployed build. A separate bounded Playwright worker captures desktop, tablet, and mobile viewport/full-page screenshots plus sanitized DOM, accessibility, geometry, style, network, performance, and interaction evidence without adding browser work to user requests.

The capture job sends the deterministic inspection header, which bypasses freshness synchronization only for that request context. It never invokes providers or writes league state. Route validation now rejects unsupported public dynamic routes and version mismatches.

Known limitation: accessibility checks use a deterministic built-in WCAG-oriented audit rather than shipping axe-core into the web process. The capture contract is designed so axe findings can be added without a schema break.

# DTOS v1.6.2 — AI Inspection System Foundation

DTOS now exposes deterministic, machine-readable descriptions of major page
structures through the AI Inspection System (DINS). These endpoints describe
what pages contain—sections, cards, tables, charts, actions, navigation, links,
empty states, warnings, and element counts—without returning raw HTML.

DINS reads the already-cached DTOS state directly. It never synchronizes Sleeper,
calls a provider, executes intelligence engines, renders page services, performs
expensive recalculation, or changes application state. Missing cached information
is represented with explicit empty states and warnings.

Initial coverage includes the inspection catalog, Team Headquarters, Player
Dossier, Front Office Intelligence, and Trade Intelligence. The inspection schema
is independently versioned as `1.0`.

See `docs/DINS_INSPECTION.md`.

---
# DTOS v1.7.0 — Market Calibration Foundation

DTOS now enumerates every cached Sleeper player and canonical future pick once, exposes each valuation layer independently, records provider evidence and freshness, and exports the live universe as JSON or CSV. Existing value and recommendation behavior remains unchanged. Unsupported or missing evidence is explicit rather than inferred.

## Previous release
# DTOS v1.7.1 - Automated Market Calibration Dashboard

DTOS now audits every canonical player and draft pick whenever market providers refresh. The new calibration dashboard summarizes integrity, freshness, provider coverage, category health, high-impact differences, and explainable recommendations. Automatic changes are limited to small category-level model adjustments and require fresh evidence from multiple providers, sufficient sample size, high confidence, and a complete asset universe. No individual player or pick can be manually overridden by this system.
# DTOS v1.8.5 — Bounded Historical Identity Context

DTOS v1.8.5 removes the historical-enrichment OOM path identified in production. Player-week enrichment now creates its diagnosable job and lease, evaluates durable season checkpoints, and constructs identity state only when eligible provider work remains.

The identity context uses a compact, streamed current-identity projection backed by the existing primary key. It no longer loads or decodes the complete version history. Normal Sleeper synchronization is idempotent for unchanged identities, while material identity and mapping changes advance separate durable generations.

The release intentionally does not delete or compact existing identity history. Migration 7 adds only small metadata structures, validates free space before applying changes, and preserves historical records, provenance, checkpoints, leases, and the canonical `5/6` enrichment state.

Validation covers checkpoint-first startup, semantic generation stability, bounded projection, recoverable preparation, disk safety, full regression behavior, and the Linux 2 GiB cgroup contract. Historical duplicate compaction remains a separately approved future migration.

---
# DTOS v1.8.7 - Canonical Historical Progress Selection

DTOS v1.8.7 makes durable season checkpoints the source of truth for league-wide historical progress. A narrow current-season refresh remains visible as job-specific `0/1` progress but can no longer replace the configured 2021-2026 league contract of `5/6` with 2026 honestly pending.

The same canonical serializer now supplies history APIs, the History page, readiness, inspection, DINS, and Asset Market historical metadata. Foundation progress and active maintenance remain separately labeled. Smoke validation also recognizes the exact bounded Asset Market warming state during registered heavy lifecycle phases, then requires eligibility, exactly one background generation, and eventual HTTP 200.

No historical evidence, checkpoints, leases, market ranking, player universe, infrastructure, storage, or pricing changed.

---
# DTOS v1.8.8 - Season-Scoped Historical Checkpoint Compatibility

DTOS v1.8.8 corrects over-broad historical checkpoint invalidation. Each completed player-week season now stores a deterministic digest of only the canonical mappings referenced by that season. Unrelated current-player synchronization no longer invalidates immutable seasons.

Legacy checkpoints migrate only after evidence presence, identity resolution, uniqueness, provenance, and record-key validation. Migration updates checkpoint and audit metadata only; importer version 1.2 event identities remain unchanged. Compatibility diagnostics expose precise sanitized reason codes, and committed material identity remaps are recorded in a durable audit ledger.

The canonical state remains five completed seasons (2021-2025) with 2026 honestly pending.
# DTOS v1.8.9 — Semantic Asset Market Artifact Identity

DTOS v1.8.9 narrows durable Asset Market compatibility to the semantic inputs that can change compact market rows and canonical decisions. Repeated synchronization timestamps, Brain generation timestamps, unrelated historical observations, checkpoints, audits, and global archive generations no longer force a market reconstruction when the consumed content is unchanged.

The durable manifest records deterministic digests for the canonical asset universe, Brain and valuation output, ownership and identity dependencies, and provider evidence. Artifact discovery now inspects final candidates through the configured storage contract, rejects incompatible manifests before row hydration, and reports precise sanitized reason codes without exposing paths or database identities.

Asset detail history continues reading the current HistoricalStore, so compatible directory reuse never hides newly captured evidence. Historical capture, immutable record identities, importer 1.2, checkpoint compatibility, canonical `5/6` progress, lifecycle warming, single-flight construction, and atomic publication remain unchanged.

---
# DTOS v1.10.4 — Durable Projection & Asset Market Restoration

DTOS now restores its normalized Sleeper state, last valid Sleeper projection
evidence, canonical Projection Intelligence snapshot, and compatible Asset
Market artifact from the configured durable production mount before optional
background refresh. Original projection timestamps and semantic identities are
preserved across restart.

Asset Market publication now records an atomic checksum manifest. Startup uses
bounded discovery with explicit pending, compatible, corrupt, incomplete, and
incompatible outcomes. Health reports restore, construction, candidate, and
publication counters without exposing private storage paths.

Projection formulas, provider parsing, Brain valuation, FOIS, Matchups, and
Historical Memory evidence remain unchanged.

## Previous release
# DTOS v1.10.8 - Asset Market No-Op Invalidation Correction

DTOS v1.10.8 prevents semantically unchanged synchronization cycles from
starting Asset Market work. Scheduler identity now follows the retained Brain
and bounded market dependencies rather than the identity of a newly allocated
cache dictionary. A final semantic-generation guard also suppresses stale or
duplicate requests before artifact loading or construction.

Health metrics distinguish rebuild requests, no-op admission skips, and actual
constructions while preserving existing counters and durable behavior.

## Previous release
# DTOS v1.10.28 - Global Sparse Market Memory & Cross-League Deduplication

DTOS now stores a meaningful asset market state once globally and links each
league-specific intelligence event to that immutable observation. Identical
states are reused across leagues, provider refreshes, and scheduled benchmarks;
material changes create a new observation immediately under one versioned
policy. Missing current evidence remains explicitly unavailable and never falls
back to a historical observation.

The migration retains all prior checkpoint evidence, links only evidence whose
equivalence can be proven, and leaves unsafe reconstructed rows embedded. New
bounded health and timeline contracts expose aggregate observation/reference
counts and storage without revealing private league context. Current Asset
Market and Brain decisions remain fresh-provider-driven and recomputable.

# DTOS v1.10.27 - HistoricalStore Physical Retirement & Disk Reclamation

DTOS v1.10.27 physically retires the dormant legacy HistoricalStore after the
Sleeper-backed history architecture proved zero production reads and writes. The
configured legacy path now fails closed on any constructor attempt and reports
bounded retirement diagnostics. A schema-verified retirement command removes only
the proven legacy database and SQLite sidecars after an explicit zero-access gate;
current season caches, intelligence checkpoints, metadata, projections, and Asset
Market artifacts remain unchanged.

The release does not redesign history, FOIS, projections, Asset Market, or
checkpoint semantics. Canonical Day Traders history remains five completed seasons
plus the pending 2026 season.
