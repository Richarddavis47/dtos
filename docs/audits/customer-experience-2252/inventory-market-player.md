# Market / player presentation inventory before implementation

Baseline e7ecd1b72944e36481668554d05dc4e321e7b3de, tree1502404775deac8eb657d62b855bbac62aed374c. Source inspection only at this stage; no owner live observations or production acquisition.

| Route/state | Existing concrete before example | Existing evidence and proposed presentation boundary |
|---|---|---|
| `/market`, complete directory | Sort choices Market / Intrinsic / Contender / Rebuilder / Confidence / Risk / Liquidity, despite unsupported modeled values. Cards already show useful identity/ownership/weekly projection/Market. | Retain usable Market ordering in normal controls; advanced existing sort choices stay optional, never invent a measure. APIs and sort semantics unchanged. |
| `/market?selected=player:…` | “Canonical Market”, “Open canonical dossier”, “Trade Intelligence”; four metrics Market/Intrinsic/Contender/Rebuilder with repeated unavailable values, “Current market values … canonical market evidence”. | Lead with Market and Sleeper projection/results; existing model/source detail in one optional disclosure. Rename action “Open player” and use existing safe exact-player Trade action; no search on open. |
| `/market` movement, current/sparse/incompatible | “Historical to current publication”, “retained checkpoints”, “value concept, scale, format, methodology or time ordering”, lengthy duplicated sparse-history and no-buy/sell caveats. | Keep supported change, actual date interval and source/age visible; concise compatibility gap. Exact clocks/reasons and checkpoint tables on demand. No comparison eligibility/calculation changes. |
| `/players/{id}` | Top identity/Market/actions/Sleeper weekly projection already good. Underneath: visible Strength Analysis, Weakness Analysis, Opportunity Analysis; season/3yr/5yr entries each say no forecast. “Active Front Office”. | Keep current projection and actuals prominent; compact strengths/meaningful risks; unimplemented forecast explanation once inside optional analysis limits; “Viewing for” franchise selector. |
| `/players/{id}` current production partial/missing | `canonical_production.production_panel` repeats a long actual-results summary, exact league and prep clocks, observation window explanations, missing score and non-Sleeper caveats. Route live panel repeats same production/projection absence in Data Availability. | One current-results answer with actual observed denominator and retained qualification beside it; windows and exact weekly coverage/source clocks optional. Preserve all numeric values, source distinction, zero/negative handling. |
| `/players/{id}` career history | Full annual table, ownership timeline, metadata and recent transactions render after the dossier even when unrelated to current task. | Optional Career History and recent activity sections, retaining source distinctions and exact contextual Back. Ownership/chronology facts untouched. |
| `/market` retained fallback/error | “earlier prepared publication”, “current matching replacement”, generation diagnostics on default page. | “Showing the last successful update” + brief reason; retain exact generation/freshness in optional sources. Do not call old evidence current. |

## Missing-data findings (bounded source inspection)

1. **Unimplemented models, confirmed:** `components/asset_intelligence.py` renders every `report.opportunity` entry (season, three/five-year horizons) even when score is None; evaluator deliberately supplies weekly-only/multi-season-unavailable explanations. No data recovery is justified. Normal presentation should stop repeating model placeholders.
2. **Unimplemented/incomplete model measures, confirmed:** Market directory exposes Intrinsic/Contender/Rebuilder/Risk/Liquidity controls and four selected-asset model metrics even if None. Existing canonical Market and Sleeper weekly evidence are independent; no substitution or value invention.
3. **Presentation duplication, confirmed:** `/players/{id}` renders `canonical_panel` and repeats its production summary in live Data Availability; absent NFLverse/usage/model fields remain a separate analysis limitation, not a reason to withhold an admitted explicit Sleeper score. The strict prepared-production contract remains intact.
4. **Genuine/unprepared current result state:** `prepared_production_context` withholds mismatched/missing actual publication. No evidence in this bounded review establishes a new ingestion/restoration defect; do not introduce a fallback.
5. **Genuine incompatible/sparse history:** trend helper explicitly preserves semantic boundaries and unknown movement. These should remain qualified with retained observations available on demand.

## Owned files / coordination

`routes/market.py`, `components/asset_intelligence.py`, `src/ui/canonical_production.py`, `src/ui/market_roster_relevance.py`, optional presentation text helpers and new Market/player-only tests. Player route is inside **`routes/transactions.py`**, approximately lines385–550: coordinate with History agent before editing that function; do not edit transaction/history routes elsewhere. Root owns common CSS and presentation helpers.

## Planned meaningful checks

Real dossier/Market TestClient fixture pages, complete/partial/missing/retained states, explicit zero and negative actuals, no unimplemented forecast cards in default-visible DOM, exact source values unchanged, actions/Market contextual Back preserved. Real Chromium at320×432/375×667/390×844/desktop using normal theme, keyboard disclosure/action focus, no overflow and default/expanded screenshots. Existing Market history compatibility and source/parity tests remain mandatory; fixtures are not live owner acceptance.

## Source wording correction before final reconciliation

The exact baseline opportunity labels in `player_evaluator.py` are **Current Season, 2-Year Outlook, Long-Term Outlook**. The earlier shorthand “3yr/5yr” above was inaccurate and is not a literal baseline quote. The confirmed problem is unchanged: all unsupported horizon entries render repeatedly. The new rendered control checks these exact baseline labels are absent from default-visible content. This correction does not alter a source fact or reconstruct original screenshots.
