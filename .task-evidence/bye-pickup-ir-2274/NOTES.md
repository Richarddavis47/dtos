# Evidence scope

The released card treated active space as independent of the roster’s Sleeper IR lock. A baseline reproduction in the normal My Team to Market flow showed 5 of 6 active spots used and no warning for a newly ineligible player occupying IR. The expected warning assertion failed on the baseline. The screenshots and raw console use only disposable fixture data.

The card now uses verified native IR placement, prepared league settings, the synchronized roster clock and the retained Sleeper catalog clock. Both clocks must be Fresh under the existing one-hour threshold. IR and PUP are supported qualifying tags. Out, Suspended, NA, DNR and Doubtful depend on the selected league’s explicit settings. Unmapped provider statuses, conflicting placement or designation, missing rules, or stale evidence produce an unconfirmed check. COV is left unconfirmed because the current published eligibility guide does not explain it.

Sleeper’s official IR article documents the roster lock and league options. The injury-status article documents PUP and the possibility of status changes within a week.
- https://support.sleeper.com/en/articles/1983643-how-does-injured-reserve-ir-work
- https://support.sleeper.com/en/articles/3570017-injury-statuses-and-ir-eligibility

An aggregate check of Sleeper’s public catalog confirmed that the general Active status can coexist with any explicit injury tag. Read-only public league settings confirmed the native flag format and contrasting rule sets. Day Traders has no IR slots. Two supported Sleeper leagues expose 10 and 3 IR slots, each allows Out and Doubtful, and their Suspended flags differ. It does not provide a live reproduction of the owner report. The controlled pickup reproduction uses a prepared league with an enabled IR slot and explicit rules in both configurations.

The implementation does not refresh the roster or catalog from the pickup page. It does not change claims, roster settings, or lineup moves.
