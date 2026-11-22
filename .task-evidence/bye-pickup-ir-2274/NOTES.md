# Evidence scope

The released card treated active space as independent of the roster’s Sleeper IR lock. A baseline reproduction in the normal My Team to Market flow showed 5 of 6 active spots used and no warning for a newly ineligible player occupying IR. The expected warning assertion failed on the baseline. The screenshots and raw console use only disposable fixture data.

The card now uses verified native IR placement, prepared league settings, the synchronized roster clock and the retained Sleeper catalog clock. Both clocks must be Fresh under the existing one-hour threshold. IR and PUP are supported qualifying tags. Out, Suspended, NA, DNR and Doubtful depend on the selected league’s explicit settings. Unmapped provider statuses, conflicting placement or designation, missing rules, or stale evidence produce an unconfirmed check. COV is left unconfirmed because the current published eligibility guide does not explain it.

Sleeper’s official IR article documents the roster lock and league options. The injury-status article documents PUP and the possibility of status changes within a week.
- https://support.sleeper.com/en/articles/1983643-how-does-injured-reserve-ir-work
- https://support.sleeper.com/en/articles/3570017-injury-statuses-and-ir-eligibility

An aggregate check of Sleeper’s public catalog confirmed that the general Active status can coexist with any explicit injury tag. Read-only public league settings confirmed the native flag format and contrasting rule sets. Day Traders has no IR slots. Two supported Sleeper leagues expose 10 and 3 IR slots, each allows Out and Doubtful, and their Suspended flags differ. It does not provide a live reproduction of the owner report. The controlled pickup reproduction uses a prepared league with an enabled IR slot and explicit rules in both configurations.

The implementation does not refresh the roster or catalog from the pickup page. It does not change claims, roster settings, or lineup moves.


## Hosted Trade fixture correction

The first hosted canonical run’s final Trade zero-result request deferred with 375,756,800 bytes available against 402,653,184 required. The original candidate’s local test completed the same journey. A matched isolated control added the same 856 MiB resident charge, used the unchanged 2 GiB cap and exercised all four viewports. Both variants passed, so the original deferral was not reproduced in the control. Closing each independent viewport’s browser reduced observed peak from 1,652,883,456 to 1,606,324,224 bytes and improved headroom on the final request from 535,203,840 to 580,278,272 bytes. It preserves all real Trade calls, keyboard and touch interactions, state, assertions, and production safeguards.

The successor changes one existing test’s browser lifecycle. The feature's application and new phone test bytes are identical to the first candidate.
