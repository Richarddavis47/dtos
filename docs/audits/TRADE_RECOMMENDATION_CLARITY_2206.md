# Trade recommendation integrity — build 2206

Baseline b4e5617b848d79ae40493bab314b6170c3f8504f (build 2205).

## Reproduction and scope

The local connected browser's list-tabs call returned UNAUTHORIZED: app connection requires reauthentication. No signed-in Day Traders tabs were read. This limitation concerns that connector, not every HTTP or browser test. No production preference or trade was changed. The exact live cause of the observed +6.31/+6.94 contexts remains unverified.

Before changes, source-pinned disposable evidence demonstrates two independent wiring faults:

* A completed current-week horizon has +6.31, but `decision_context` erases it when the stricter availability diagnostic's `numeric_impact_state` is unsupported. The same completed result still explains meaningful improvement and renders weekly numbers. The diagnostic branch is explicitly controlled, not a claim that the live account had that precise missing source. The corrected comparison preserves its number as conditional, not dependable cover.
* `recommendation` is a user-side conclusion. The existing classifier and generated-trade eligibility already reject a counterparty-limited offer, but the shared renderer and alternative-card heading print that user-side label. An actual Custom adapter pick-exchange fixture reproduces positive user upside and LOW neutral counterparty plausibility with eligibility false. No gate or threshold needs changing.

## Correction

`services/trade_decision.py` publishes one final presentation contract from the existing classifier/eligibility. Favorable user-side labels with failed bilateral admission cannot be primary endorsements. Raw user-side labels remain unchanged and are labelled as supporting context. Existing rejected and qualified cases retain their conclusions.

The prepared lineup comparison and roster-availability diagnostic are separate evidence dimensions. Current-week delta, requested weeks, season, league/scoring identity, generation and availability qualification are carried together. Missing/incompatible horizons remain missing; other windows cannot stand in for the current week. Generation/league conflicts withhold the presented comparison. No projection or additional lineup is calculated by the formatter.

The server explanation, main client result, preview and alternative-card headings use final qualification. The older-response client fallback also refuses promotion of a recorded ineligible offer. Source and revision fencing, retained/not-revalidated contexts and exact package identities are unchanged.

Current-week comparisons name their season/week. Other windows name the weeks and say total across the window; averages name the union of supported weeks. Availability remains conditional where stricter usable-roster evidence is not supported. Raw legal-lineup totals retain their accepted precision; derived deltas use the existing readable point formatter.

## Preservation and acceptance

Focused controls cover exact illustrative 608+334=942 sent /931 received, 11 Market overpay, +6.31 current week and +6.94 another week, missing versus zero, incompatible generations, Neutral/Custom and explicit strategies, actual saved intent/private HTTP/client rendering and an unseeded strategy comparison on one publication. The fixture is not a live valuation or acceptance prediction.

Existing 995/75 severe-overpay, justified +4/+8 consolidation, useful reserves, exact picks, missing-price/material-benefit and neutral opponent evidence controls remain required. The supported personal conclusions and raw recommendation/eligibility fields are not rewritten for cosmetic consistency. Historical evidence and FOIS grades remain RETAINED / NOT REVALIDATED.

Four-viewport Chromium controls cover 320x432,375x667,390x844,1280x900, native keyboard disclosures and visible focus, selection, Neutral/Custom switching, unchanged saved state and no document overflow. Physical iPhone/Safari and live authenticated acceptance are not established. Existing discovery-quality limitations are not redesigned; no target or Derrick Henry is seeded into Recommended controls.

Repeated formatter controls guard six expensive operations and verify no mutation. There is no schema, cache, provider, worker, solver, background work or persistent history change. Actual 2 GiB canonical/lifecycle CI is mandatory; passing fixtures must not be described as broad production memory/latency clearance.

## Attempts retained

Initial new fixture swapped the wrong rank slots and correctly produced REJECT; the fixture was corrected to use favorable existing slots. Browser setup initially double-closed an already stopped Playwright browser and failed to open the nested weekly disclosure. Those harness defects were corrected without removing focus/visibility assertions. Old missing-Market tests expected the very favorable primary label this task prohibits; assertions now require an unavailable primary conclusion plus the unchanged, separately labelled user-side WORTH PURSUING. A subsequent renderer regression classified a missing weekly value as partial-supported; it was corrected to preserve UNAVAILABLE for null, and preservation controls rerun. No test was skipped or assertion weakened to endorse a bad offer.

Full mandatory regression, all ten canonical gates, hosted Product/security/browser, historical and resource/lifecycle checks must pass on the exact release candidate before merge. Final counts, source/tree identities, resource series and unsuccessful attempts belong in the accompanying Scout handoff.

The first hosted My Team run exposed an older consolidation presentation assertion: the existing fixture's +8 gain and user-side WORTH PURSUING coexist with LOW counterparty support and generated eligibility false. The strengthened assertion preserves the gain, reserve cost, package assessment and user-side label while requiring a COUNTERPARTY LIMITED primary verdict. Expanded older cached HTML is also qualified using its recorded admission, without re-evaluation. The final conclusion's evidence key points to bilateral qualification, independently of the user-side assessment record.
