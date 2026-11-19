# Upcoming bye weeks in v1.22.54 / build 2269

My Team uses the recorded starting slots for the next two scheduled weeks of bye planning. The disclosure names each affected starter and shows the moves that produce one legal lineup, including any FLEX or Superflex rearrangement. It links to the selected week's Matchups and keeps an explicit assessment for a shortage, incomplete evidence or a week without a starter on bye. Missing projection points and incomplete schedule or roster evidence are shown separately.

- PR #358. Candidate `e6a0dccdf1614c2fb62622f0e53c13511f68530e`.
- Deployed commit `7049c0d52520f4a89d1c604446e7a6a35aa6cca7`, validated tree `d35184f4c563b95d7fc49287eb67d1b240058899`.
- Immutable release https://github.com/Richarddavis47/dtos/releases/tag/v1.22.54.

Nineteen focused cases passed. Both local and hosted canonical runs passed 4,654 tests and ten gates under 2 GiB. The required hosted jobs, publisher controls, public readiness and smoke checks passed. The phone navigation limit and overflow assertions ran unchanged. Earlier fixture setup and validation attempts retain their own original logs.

For an owner check, compare the selected weeks and each affected player's bye with Sleeper. Reconstruct a legal lineup from the recorded roster, using each player at most once and respecting slots and eligibility. Compare that result with the planner before following its Matchups link.

The rendered feature acceptance used a disposable fixture at 390px with Chromium touch and keyboard interaction. This session did not have a supported already prepared owner session. Physical iPhone/Safari and private production source parity remain unverified. No forced entry or sync and no lineup changes were performed.

# Scout acceptance for bye-week moves

PR #358 · candidate `e6a0dccdf1614c2fb62622f0e53c13511f68530e` · validated tree `d35184f4c563b95d7fc49287eb67d1b240058899`.

In an already prepared owner league, open My Team and expand **Upcoming bye weeks**. Compare both target weeks and the listed starters’ byes with Sleeper. Apply every proposed move together on paper. Each player should occupy one eligible league slot, and each named starter on bye should leave the lineup. Check FLEX, Superflex and repeated slots when configured. With insufficient evidence, expect a qualified result. Follow the week’s Matchups link, then use Back to return to My Team. Leave submitted lineups and settings in place.

Repeat with the disposable fixtures. Week 9 shows the WR on bye in FLEX and the eligible RB who can take that slot. The Superflex fixture moves the incumbent Superflex player to RB and starts the bench QB at Superflex. The other cases cover simultaneous byes, a true shortage, missing schedule or eligibility, roster order, and stale prepared inputs. The responsive check uses 390px Chromium emulation. Record owner observations and physical iPhone/Safari separately.
