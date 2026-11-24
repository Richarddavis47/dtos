# Scout acceptance for signed-in Home

[PR #365](https://github.com/Richarddavis47/dtos/pull/365) · [Source identities](source.json)

1. Open Home with a disposable signed-in fixture. At 320px, 390px and desktop, check the brand and league switch on one row, team name and three stats, and one prominent **Do this first** card. Verify direct access to My Roster, Trade Center, this week's matchup, and the bye planner. Confirm all five primary links remain available. The league switch must use the authenticated active membership.
2. Prepare a legal lineup replacement with a near kickoff. Check that it leads ahead of an upcoming bye and a roster or trade opportunity. Let the lineup evidence expire. The recommendation must retract and keep keyboard focus. Verify confirmed bye cover and a shortfall use the prepared plan. Conditional cover must say it depends on availability. When there is no supported action, check the calm roster link.
3. Confirm Home sends no trade-discovery POST by itself. Open **Front Office Brief and trade tools**. Check that prepared suggestions, rationale, uncertainty and the deliberate trade action still work. Verify standings, team comparisons, matchup previews, activity, assets, and Market links remain accessible farther down.
4. On a recent completed exchange, read the team labels, completion date, **Market edge** date, center tick and verdict. Check both edge directions and Even. Verify a partial or incompatible package, a waiver-budget component, and multi-party trades have a plain reason instead of a winner.
5. Expand **Why this edge** with Enter and emulated touch. Verify received assets and costs, exact picks where present, and source qualifications. Follow **Original trade**, use contextual Back, then open **View all trades**. Verify no overflow and unobstructed focus.
6. In a public session, open Welcome and each of the three read-only demos. If production access is available later, separately record an authenticated owner fixture comparison and physical iPhone/Safari results.

Screenshots and consoles use disposable Chromium fixtures. The captured baseline signed-in Home comes from the previous release’s exact-source visual evidence. Before and after trade cards use the same retained completed-trade fixture. Mockup names and example values are illustrative, so independently verify each rendered figure against the prepared source.

Exact final candidate `96c9697a865d9725bb8d9e3a5c403530bad80b76`, tree `9bf70f099ca65ea9a137fdda1b8cf60f0335353c`. The fresh disposable Chromium captures and seven focused checks are tied to that source. The shared header and primary-action markers were restored after the prior candidate failed its HTTP smoke. The original failed run and the partial superseded local run are kept separately. The unchanged HTTP smoke and nine focused checks passed on the corrected application bytes before the final exact-source runs.

The desktop layout keeps the established top navigation. Phone captures use the existing fixed bottom navigation. At the shortest 320px viewport, scroll to reveal content below that navigation. Verify the primary action and focused controls scroll into usable view.

## Release and verification

- The immutable release is **v1.22.61 / build 2276**. Production reports commit `23a11f18f5b95633e90291a9351f258caa3b7f7d`. The annotated tag and deployed commit resolve to the same validated application tree. [Release](https://github.com/Richarddavis47/dtos/releases/tag/v1.22.61)
- Local and hosted canonical each passed 4,672 tests and all ten gates under 2 GiB. All 13 required hosted checks passed. The seven directly reviewed fixture checks cover Home priorities and completed trades. The Product Browser job passed 1,085 checks. The publisher unit run passed 182 checks.
- Both publisher stages verified 23 attachments. Production readiness, welcome and sign-in passed. Private routes rejected unsigned requests. [Guarded prepare](https://github.com/Richarddavis47/dtos/actions/runs/45293236188) · [Guarded publish](https://github.com/Richarddavis47/dtos/actions/runs/45294333195)
- Production verification used public read-only endpoints. Signed-in owner acceptance and physical iPhone/Safari were unavailable. Use the linked disposable fixtures when checking signed-in Home.
- For readable evidence verification, run `sha256sum -c SHA256SUMS` in this directory. [Original consoles](originals/) · [Before screenshots](before/) · [After screenshots](after/) · [Release records](release/) · [Prior attempts](originals/superseded/)
