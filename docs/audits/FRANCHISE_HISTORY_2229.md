# Franchise transaction history — build 2229

## Baseline and evidence scope

Production readiness and origin/main both confirmed v1.22.13/build 2228, commit 6b43bfa183ed9a2023ecb59247c8831da3c4b1dd, tree 0764486d9440d39438a615ef301ddafe3a30a7fd. No authenticated production league entry, source synchronization, Trade search or saved-state mutation was performed.

Controls reuse tests/fixtures/trade_timeline_sources.json: read-only Sleeper captures dated October 12, 2026, explicitly partial transaction fixtures. Day Traders (1313066632158924800) and Arkham Asylum (1319750579458686976) are replay controls, not current live completeness claims. The existing FAAB fixture supplies an independently retained 2023 event. Controlled synthetic linked seasons exercise missing, malformed, complete-empty, ownership-change and exact-pick cases; those are not reconstructed real historical seasons.

The original baseline console records three retained Day transactions/40 league selections and zero Arkham transactions/260 league selections; neither original Franchise History page rendered those event records. A probe subsequently reused the baseline output directory: its original console remains intact, but original HTML/report files were overwritten. Candidate output is retained separately, and a new baseline replay uses the exact original source tree and is explicitly recreated evidence. No production evidence was overwritten.

## Confirmed gaps and corrections

* Franchise History showed only identity, roster and optional intelligence snapshots. The new bounded timeline exposes supported source events on that same surface, preserving existing sections and links.
* HistoricalAssetGraph.franchise_history classified seasons as complete solely by calendar age. A shared transaction-acquisition summary now distinguishes Complete, Partial and Unknown using actual retained source periods and closed-season/identity evidence. It does not grade a franchise.
* Transaction archive rows offered a completed trade dossier link for noncompleted trades. Links now require explicit completed status and readable consideration; completed-trade entry links explicitly apply the completed filter. Noncompleted or malformed records do not establish asset movements.
* A source-period list with missing IDs, unknown status or conflicting identities cannot justify an empty-history claim. Known failed/rejected/pending records remain visible separately. A genuine zero FAAB transfer remains numerical zero.

## Exact source path

Sleeper season links/discovery manifest and retained cache -> CanonicalHistoryStore typed records and transaction_coverage -> existing status/identity admission from summarize_activity -> source- and transaction-scoped deduplication -> Franchise History view and existing Trade Ledger filters.

transaction_coverage borrows only existing compact league/transaction sections and reads existing discovery metadata. It preserves prepared current bucket evidence separately from a flat activity list. Same-league/season current buckets can augment retained buckets; unavailable refresh buckets preserve last-valid source data with a qualification. Cache generation and prepared-current fingerprint are separately identified. Missing optional families never trigger a new all-family player-week/graph projection in the new view.

Exact trade picks use the canonical future_pick_id contract. Draft selections use its selection=True mode, independently preserving original-roster evidence; selecting ownership never becomes original identity. Unknown originals stay unknown. Selection time is never inferred from whole-draft lifecycle bounds. No retrospective grade, trade-benefit allocation or historical price is computed.

Existing reconcile_ownership rules use actual previous-league links and roster slots. Season-observed owner changes have no invented takeover dates. A missing intermediate link does not erase valid completed source facts: they appear as source-roster observations with unconfirmed connection to the current franchise and no current-manager credit. A changed source epoch during assembly withholds completeness and empty conclusions while retaining individually supported facts.

## Coverage meanings

Complete transaction coverage requires all supported buckets 0–18, no missing/unavailable/malformed periods, a completed compatible source season, and no unqualified/conflicting/unknown-status source records. A complete franchise no-activity conclusion additionally requires observed identity and established continuity. Current or older calendar year is insufficient. This is the supported source-bucket scope, not a guarantee about provider activity outside that scope or updates after the retained snapshot.

Draft selections have their own observed counts. Complete transaction acquisition does not imply every draft selection, owner tenure, weekly roster or historical grade is known. Unknown and partial remain distinct; a source timestamp is not fabricated when only source identity/generation is retained.

## Verification and remaining limits

Focused controls cover complete, partial and unknown rendered pages; actual Day/Arkham replay; completed waivers; failed/pending/rejected/unknown records; duplicate and conflicting IDs; exact traded pick original differing from owner; auction unknown original; observed manager change; missing continuation with independently retained movements; malformed consideration; missing historical identity; wrong source season; current prepared buckets versus flat activity; source-publication changes; no provider calls, full graph construction, historical pricing or regrading. Chromium covers 320×432, 375×667, 390×844 and desktop, keyboard/touch emulation, focus, no overflow and no disclosure requests.

Original failures and exclusions remain separate from final exact-source mandatory evidence. One pre-existing unique-asset-count test caught a changed phrase; wording now preserves the count and explicit noncompleted qualification. Development lint diagnostics and the baseline probe-output limitation are retained in the task evidence. Full canonical, hosted and constrained-memory outcomes are published only after actual completion.

Private live franchise-history acceptance remains unverified. Physical iPhone/Safari is not claimed. Cleanup measurements are not indefinite leak-freedom proof. Provider absence, historical ownership continuity and missing exact selection times are not repaired by presentation.

## Scout acceptance

1. Verify deployed version/commit/tree and immutable evidence checksums.
2. On retained Day Traders and a second authorized league, inspect season coverage and a completed source event. Match its source season/ID and retained completion status; do not initiate synchronization from an ordinary read.
3. Confirm unknown/partial source periods do not become no activity, and draft coverage remains separate. Known-empty closed-period fixtures provide the complete control.
4. Verify a moved pick's original franchise differs correctly from its owner; confirm source-roster/manager qualifications across missing links or ownership changes.
5. Inspect pending/rejected records in the separate disclosure, no completed dossier/movement inference, retained FOIS qualification, responsive focus/touch behavior, and unchanged saved user state.
