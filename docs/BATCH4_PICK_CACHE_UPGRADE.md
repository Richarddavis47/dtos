# v1.18.1 bounded production correction

v1.18.0 (b90d38e) passed release gates and deployed. Authenticated production
smoke passed, but live Picks showed NO_VALID_PREPARED_PICK_PRICE.

Read-only production cache inspection found no pick quote families. Both public
providers were healthy and last retrieved on 2026-09-13 at 18:52 UTC, with their
next refresh scheduled for the following day. The pre-upgrade cache therefore
suppressed first materialization of the new evidence family.

A focused healthy-cache fixture reproduced the missing FantasyCalc family before
correction. The fix tests family presence independently from normal refresh age.
It does not treat a successfully fetched empty family as a missing one. Failed
fetches retain disclosed player fallback, do not manufacture pick prices, and
do not alter another provider's retained evidence. Provider effective timestamps
are unchanged by cache reads.

No production cache was manually edited. No new access mechanism or evidence
transfer was used. v1.18.0 is immutable; production acceptance remains open.
