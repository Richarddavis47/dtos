# Scout acceptance for build 2275

Candidate `222f453fd1cdb3db2efb6241852354609bc26463`
Validated application tree `161e801ae284ec307bb960e3ff9dbb8511680347`
Baseline v1.22.59 / build 2274, commit `d18abdcf6c9f8a83abf0a63a422b617f8b4801fb`
[PR #364](https://github.com/Richarddavis47/dtos/pull/364)

1. On a prepared full roster, open My Team, expand **See weeks and possible moves**, and follow the Week 9 pickup link. On **Free Runner**, open **Compare a drop**. Choose a player from an active roster spot. The IR player must not appear in the dropdown. No player is selected on the manager’s behalf.
2. Select Example R 1 and preview. The proposed lineup fills RB 1 and covers all slots. Example S 1 is questionable and appears as a dependency. A supported fixture price of zero appears in the separate outgoing Market section.
3. Select Example W 1 to see the newly uncovered FLEX. Select Example Q 1 to see that absent schedule support prevents confirming QB cover. In the Superflex fixture, dropping the only movable RB leaves the original RB gap open.
4. Verify the active roster count and confirmed IR blocker remain visible. Returning the ineligible IR player would still require one more active spot in this fixture. Read this as a preview only. Claims, adds, drops and IR moves stay in Sleeper.
5. Use contextual Back after multiple previews and confirm Week 9 is still expanded. Verify the 390px layout and keyboard/touch controls. Record signed-in owner observations separately if an already prepared production context is safely available.

Legacy publications without the comparison basis cannot substantiate this preview until regular preparation updates them. Prices also require a compatible prepared Market publication. Browser fixture screenshots do not constitute signed-in owner or physical iPhone/Safari acceptance.

## Release and verification

- The immutable release is **v1.22.60 / build 2275**. Production reports commit `a3a859bc5d316eb5382ff6ab80b0cfc763275adf`. The annotated tag and deployed commit resolve to the same validated application tree. [Release](https://github.com/Richarddavis47/dtos/releases/tag/v1.22.60)
- Local and hosted canonical each passed 4,668 tests and all ten gates under 2 GiB. All 13 required hosted checks passed. The 24 focused checks included the 390px Chromium pickup, comparison and Back journey. The publisher unit run passed 181 checks.
- Both publisher stages verified 23 attachments. Production readiness, welcome and sign-in passed. Private routes rejected unsigned requests. [Guarded prepare](https://github.com/Richarddavis47/dtos/actions/runs/45092417107) · [Guarded publish](https://github.com/Richarddavis47/dtos/actions/runs/45092753096)
- Production verification used public read-only endpoints. Signed-in owner acceptance and physical iPhone/Safari were unavailable. Use the linked disposable fixtures when checking the comparison.
- For readable evidence verification, run `sha256sum -c SHA256SUMS` in this directory. [Original consoles](checks/) · [Screenshots](screenshots/) · [Release records](release/) · [Prior attempts](prior-attempts/)
