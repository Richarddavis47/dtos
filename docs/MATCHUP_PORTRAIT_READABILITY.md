# Matchup portrait readability — v1.21.32 / build 2132

Baseline: v1.21.31 / build 2131, `50d8d6a3e507aa860d6c4a2b7843650b92bf7f9e`.

## Cause and correction

The shared identity component reserves 52px for its portrait, image and absolutely positioned fallback initials. Matchup CSS previously reduced only the wrapper and image to 28px. The fallback remained 52px behind the loaded image and could extend into adjacent text.

Only `.matchup-player` styling changes: the wrapper remains a non-shrinking 28px square with rounded containment, and both image and fallback fill that wrapper. The existing image `object-fit: cover`, lazy loading and failed-image fallback behavior remain intact. Names and status/projection labels retain wrapping; no important text is hidden or truncated. Shared My Team/dossier portrait styling remains unchanged.

No scoring, projection publication, roster selection, standings, probability, Trade intelligence, authentication or persistence code changes.

## Rendered acceptance

`tests.test_matchup_portraits_browser` exercises the actual matchup router and shared identity renderer with controlled image transport. It verifies loaded, pending, failed and fallback-only images; long names/status; available actual and projected values; unavailable projections; empty slots; both sides; visible starters/bench/IR/taxi; keyboard dossier activation and focus; pointer hit-testing; return navigation; and document overflow.

At 320×483, 320×844, 375×432, 375×812, 390×677, 390×844 and 1280×757, DOM bounding rectangles must show 28×28 wrappers/images/fallbacks, graphics contained in the wrapper and no graphic intersection with identity, position/status or point/projection text. A non-matchup control retains 52×52 shared portrait/fallback geometry. The original CSS fails all seven sizing subcases; corrected CSS passes.

Additional read-only Sleeper source samples render Week 5 matchups from Day Traders (`1313066632158924800`, matchup 3) and Arkham Asylum (`1319750579458686976`) locally using the production router. Those checks include reload and the same geometry assertions. Image transport is controlled and source-only projections are unavailable, not invented. This is source-backed local rendering, **not authenticated production browser acceptance**.

Run focused verification:

```bash
python -m unittest tests.test_matchup_portraits_browser tests.test_matchups_phone tests.test_matchups_phone_browser tests.test_matchup_evidence_contract tests.test_matchup_browser_contract tests.test_batch6_matchup_browser tests.test_dossier_status_browser tests.test_phone_visual_corrections_browser
```

The new browser contract also runs in Product browser CI and full regression. Required canonical and 2 GiB lifecycle gates remain unchanged. Responsive Chromium does not establish physical iPhone/Safari acceptance or accessibility certification.

## Scout independent live handoff

Verify Settings release identity before testing. Day Traders → Week 5 → Chase Bank versus Connecticut Clams (`/matchups/3?week=5`): inspect Bo Nix/Jameis Winston, Bijan Robinson/Jaylen Warren and Omarion Hampton/David Montgomery.

Measure `.player-portrait`, `.player-headshot` and `.player-headshot-fallback`: all visible graphics must fit the 28px reservation, including after reload, during loading and when requests fail. Names, position/status, actual values and Sleeper projection labels must remain readable. Repeat at 320/375/390px, taller portrait and desktop, plus a matchup in Arkham.

Check player pointer/keyboard navigation and same-week return; full roster sections; official totals excluding nonstarters; submitted versus optimal lineup labels; unchanged Home/League standings; shared My Team/dossier portraits; sampled Trade/Calculator prices, exact protections, preview/Keep Original/Adopt and FOIS retained-grade disclosures.

Distinguish signed-in live observations from source/fixtures and responsive Chromium from physical iPhone/Safari. Existing historical grades are untouched; this rendering fix does not validate their numerical correctness.
