# Team Assessment Coverage — deployed acceptance handoff

Released **v1.22.12 / build 2227**. PR #316 merged. Production readiness confirmed commit `40226bb497a5b5c30047cc5f98e49c4008c67992`; its tree `de2827e28dea58e7174c938ba4b38930e0892bea` exactly matches validated candidate `40cea1690943cca2ba1b99b50612c5ae6b5c68ac`.

Immutable release: https://github.com/Richarddavis47/dtos/releases/tag/v1.22.12
Prepare/readback: https://github.com/Richarddavis47/dtos/actions/runs/41926751116
Publish/deployment: https://github.com/Richarddavis47/dtos/actions/runs/41927187702

Acceptance checklist:
1. Verify production version/build/commit, immutable tag and identical candidate/merge tree; verify the attachment checksums and original canonical manifests (559 local, 563 hosted).
2. On both Home and My Team, verify a coherent complete comparison and the disposable incomplete case: 9/10 slots and 1/2 comparable teams remain visible, no incomplete total or projected rank, expanded text says prepared but incomplete and names DEF only when supplied. Keep official standings distinct. Verify genuinely missing comparison wording separately.
3. Review availability-change, aging and failed-refresh rendered controls in `tests.test_team_assessment_presentation`; points/rank agree or rank is withheld, provisional label/reason survives, and the saved profile remains unchanged.
4. Review responsive Chromium/keyboard/touch evidence at 320×432, 375×667, 390×844 and desktop. Physical iPhone/Safari and authenticated live franchise acceptance were not performed here. Use normal read-only warm-page inspection if available; no forced hydration, Trade search, sync, FOIS rebuild or preference mutation is needed.

Final evidence: 65 focused tests, 4,066 local and hosted regression tests, all ten gates in each, all twelve hosted jobs, 595 Product executions, 40 publisher guard tests and five exact-source 2 GiB preflight cases. The unchanged 100 ms fixture scheduling control initially measured114.145 ms once; 20 isolated repeats measured 4.691–7.613ms and a full clean retry passed. Cause of the one excursion is unproven; original failures are separate and readable.

Cloud signed artifact/job-log redirects returned Forbidden; the established native Actions publisher verified original archive digests, payload manifests and all 16 attachment byte readbacks. A single early Cloud readiness sample returned HTTP 502; later exact-version readiness and both native/independent bounded smoke checks passed. These are observations, not a diagnosis of that sample's cause.

No overall grading, scoring, Trade math/qualification, submitted lineups, account preferences, rankings, valuation methods or admission reserves changed. This release does not establish Granite entry recovery or the cause of the earlier503. No production user-data mutations or heavy production workloads were performed.
