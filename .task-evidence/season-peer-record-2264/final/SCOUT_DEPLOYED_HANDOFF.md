# Weekly league score comparisons — v1.22.49 / build 2264

The Season so far disclosure on My Team now counts how often the franchise outscored, tied, or was outscored by each other team. Only completed regular-season weeks with the full compatible league cohort qualify. An eligible week contributes one comparison per other franchise. Skipped weeks are listed and incomplete coverage stays visible. The official record, median games, and current projections retain their own meanings. Home keeps the existing season summary and link.

- PR #353. Candidate `9324d761b9ea065d751549774f3f44d32463e1f3`.
- Validated tree `1057964151b6a9b7e6f1737c7c280d666569d972`.
- Deployed commit `5396b1d20f318a05f34b72cd6734d9b132f51fd7`.
- Immutable release https://github.com/Richarddavis47/dtos/releases/tag/v1.22.49 with 23 verified attachments.

Focused checks passed 23 tests. Local and hosted canonical each passed 4,634 tests and ten gates. All 13 required hosted jobs passed, plus 181 publisher controls. The enforced local 2 GiB limit recorded a peak of 1952624640 bytes. The 600px roster placement and overflow checks remain in force. Public deployment readiness and smoke checks passed.

Owner score parity is unverified because this session exposes no authorized prepared owner browser or Render Shell. No league sync or data mutation was made. Screenshots are Chromium emulation, with physical iPhone/Safari untested. The initial successful wording run is preserved separately from the committed result.

# Scout acceptance — weekly league score comparison

PR #353. Candidate `9324d761b9ea065d751549774f3f44d32463e1f3` and tree `1057964151b6a9b7e6f1737c7c280d666569d972`. Build 2263 baseline `d21327682a892826404d0d72531c1cb0e9582fe5`. Check the final receipts before recording a deployed identity.

1. Open Home in an already prepared league and use Review season results to reach My Team. The roster remains ahead of Season so far. Expand “How often did we outscore the rest of the league?”. Verify keyboard activation, narrow layouts, and the distinction between the official record, any median game, and score comparisons with every team.
2. Recompute from compatible native Sleeper team matchup scores for completed regular-season weeks. Use an explicit valid custom score when present, including zero and negative values. Compare the selected team once against each other distinct league roster for that week. Keep ties separate. Skip an entire week if a team is missing, ambiguous, or has a conflicting or invalid score. Confirm included and skipped week counts and means independently. The comparison count should equal the included week count times the number of other league franchises.
3. Use the rendered fixture and original focused logs for independent controls. A 4–0 official record can coexist with 4 wins and 8 losses against peers. A 0–4 record can coexist with 8 wins and 4 losses against peers. Test four teams and median settings, a zero override tie, a negative override, correction, duplicate score row, missing and conflicting peers, and suppression when no week qualifies. Retained results stay qualified. Official standings and current projections remain separate.
4. Check all mandatory canonical, hosted and publisher receipts, exact release tree and original log checksums. Headless Chromium screenshots are fixture evidence. Record authenticated live observations and physical iPhone/Safari only if actually performed.

Owner verification requires an existing safely prepared authorized context. Leave settings and league data untouched, keep Render credentials inside Render, and stop on admission deferral. Avoid any manual sync, cold entry, Trade search, or rebuild. If access is unavailable, record it and use the independent source fixture and public readiness checks within their actual scope.
