# v1.14.1 Matchups correctness boundary

This release addresses three production findings from v1.14.0: pregame zero-actual
ties masking unequal projections, absent forecast bounds presented as zero ranges,
and starter identities lacking dossier actions. v1.14.0 remains immutable.

## Evidence contract

- Pregame starter badges compare the active league's canonical player projections.
  A missing participant forecast is unavailable, not an even battle.
- Live badges compare actual scoring; final badges describe actual final results.
  Explicit live/final source state takes precedence over a preseason/zero heuristic.
- Forecast totals and ranges require every contributing value; zero is accepted
  only when supplied numerically. Partial canonical totals retain coverage labels
  but do not decide the full-team projected winner.
- Missing bounds do not manufacture volatility rankings. Positional comparisons
  omit incomplete evidence rather than treating it as zero.
- Player names/portraits use existing `/players/{id}` routes, native anchors,
  visible focus and at least 44px touch targets. Missing IDs create no fake link.
  Existing franchise and matchup navigation remains in the active league context.

## Focused evidence

- 65 focused evidence/presentation/projection/inspection/navigation tests passed.
- Real Chromium mobile (390×844) and desktop (1280×900) proof passed: no horizontal
  overflow, keyboard Enter/click dossier navigation, team navigation, matchup return,
  and adequate player tap targets. Browser resources close in `finally`.
- The initial focused run exposed an obsolete zero-range expectation in an empty
  projection fixture. It now explicitly requires null bounds/totals.
- A browser-fixture missing charset misdecoded the back-arrow accessible name;
  declaring UTF-8 fixed the fixture without changing production navigation.
- Additional missing-player fixture lookup and test placement mistakes were fixed
  narrowly; failing logs are retained as evidence, not counted as passes.

FOIS, checkpoint reuse, historical evaluation, Market admission, resource limits,
authentication and membership semantics are untouched. The accepted 30.557-second
v1.14.0 cold FOIS preparation proof remains applicable. No Current Visual, DINS,
or External Visual Mirror system is restored. Full release/production gates must
still pass before acceptance is complete.

## Canonical gate evidence

The first canonical invocation passed full regression (517.965s), compile, Ruff,
dependencies, whitespace and routes/OpenAPI (250 registrations, zero duplicates,
234 paths). HTTP startup passed; HTTP smoke failed the unchanged 500ms warming
gate before any Matchups route ran. Request `e279f8feceda4a7ead4fdb874c37a823`
at 2026-09-07T07:23:11Z took 1,014.858ms client / 0.341ms server header timing
(0.356ms request-log timing). The preceding 23 warming requests took
2.880–12.761ms. Non-handler duration was 1,014.517ms, almost entirely before
headers, during initial synchronization. This proves an outside-handler delay,
not its exact scheduler/transport cause. Cleanup and process verification passed.
Run ID: `e35be96c2d2642a185915262a2bed337`. The red event remains recorded.
One unchanged HTTP-only recheck follows under the standing bounded-recheck policy;
no source, workload, threshold or fixture changes were made to obtain it.

The bounded HTTP-only recheck passed unchanged, run
`e2a8d6d9efc24def98319ec41731d794`: startup 6.009s, HTTP smoke 109.987s,
cleanup 14.425s, and process verification passed. The original canonical invocation
remains a failed event; its eight passed gate results are reused on the unchanged
product/test boundary, with the independently passed canonical HTTP worker and
final process check completing the required local gate set. No duplicate full
regression was run to replace valid evidence. Linux/PR/production gates remain.
