# Post-trade eligibility and source aging

This correction preserves v1.21.50's legal solver, player projections, Market
prices, strategy precedence and bounded storage contract.

## Admission and package evidence

Both sides' complete proposed rosters pass through the existing canonical
availability admission after all player movements. PRE and POST eligibility
retain named identities, statuses and exclusions separately. Incoming
Unknown/Questionable/Doubtful evidence qualifies conditional numerical impact;
Out/Inactive/Retired players remain owned assets but not usable cover. Removing
uncertain players removes their uncertainty from POST evidence. Picks remain
capital, not projected players. Capacity and canonical horizon evidence stay
separate from availability-qualified current-week assignments.

## Original source clock

Canonical `source_timestamp` is evaluated at read time in UTC: Fresh before one
hour, Aging from exactly one hour, Stale from exactly six hours. Unknown, invalid,
naive or future observations are unavailable. Explicit retained/fallback source
qualifications remain separate. Publication, retrieval and refresh-attempt clocks
never replace the original observation.

Numerical diagnostics keep the existing 12-entry / 2 MiB / 180-second cache.
Returned explanations are cheaply requalified without solving again when only
source age changes. Team/HQ/League explanation caches and retained Home
opportunities include that qualification boundary in their read identity.
They cannot freeze Fresh across an age boundary. No hidden Home discovery starts.

## Failed refresh

The projection service exposes its existing in-memory failure evidence for the
exact retained league/publication. A failed or incomplete preparation preserves
the last valid publication and original source clock. Failure qualification is
separate from Fresh/Aging/Stale and numeric usability. A successful publication
clears the failure; absent evidence never becomes an inferred failure. No
permanent refresh-event history or additional publication store is introduced.

## Independent acceptance

Reproduce the actual 20→28 receiver control with Active/Unknown/Q/D and unavailable
incoming players; inspect separate PRE/POST evidence in HTTP and rendered Trade.
Use deterministic clocks immediately before, at and after 1h/6h, warm and cold,
without publishing new projections. Verify retrieval-only changes do not reset
age or recompute numerical lineups. Test failed preparation, retained head,
recovery and foreign-league rejection. Preserve valid zero, missing scoring,
14/15-starter and 2,048-player guards, exact picks, forced cuts, Superflex and
retained FOIS contracts. Check My Team/HQ/Trade at 320/375/390 and desktop.

Codex-hosted isolated ASGI/Chromium evidence is separate from Scout-independent
authenticated production and physical iPhone/Safari acceptance.
