# Prior author focused attempts — retained failures

These earlier logs are development history, not final candidate acceptance.
`browser-first-original.log`: comparison helper tried Calculator's hidden phone side tabs.
`browser-second-original.log`: source836d036 reproduced the known Recommended-protection lock leak before the combined6e9548b fix.
`browser-third-original.log`: the authored keyboard test had not entered keyboard modality before checking focus-visible.
`browser-fourth-original.log`: the final authored assertion indexed an optional absent field instead of admitting an empty workspace.
`focused-all-original.log`:23/24 passed; the new Superflex navigation predicate dereferenced a not-yet-arrived DOM element. An exact URL/readiness wait corrected this test race.
These failures were preserved. The final clean source52-test focused result and its current native captures are separate under `final/`.
