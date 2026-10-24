# Custom Rankings compatibility and recovery

My DTOS saves a manager's exact asset order, optional tier boundaries and sparse
Target/Avoid/Protect choices. Current compatible Market evidence supplies the
personal valuation context. An ordinary Market update does not reset or reorder
the manager's saved preferences.

## Why a saved order can need attention

A personal ranking uses the descending current Market price slots of the same
saved asset cohort. If a saved asset no longer has compatible identity, status,
price or exact-pick ownership evidence, assigning the remaining price slots to
the unchanged order would invent a value or misalign the cohort. Custom numeric
evaluation therefore remains unavailable until every ranked asset is supported
or the manager explicitly changes the cohort. Neutral Market calculations remain
available and unchanged.

The compatibility review names each affected exact asset and explains the
observed reason. A missing Market price is different from a supported zero. A
missing row is not proof that a player retired. A current status explicitly marked
retired or inactive, conflicting identity/ownership evidence and a missing price
receive different explanations. Source-generation mismatch is a context-level
qualification; retrying does not establish compatibility by itself.

The currently eligible Market count and saved-order count can legitimately
differ. A newly eligible asset is not inserted into the manager's saved order or
given a personal value automatically. A change in displayed asset count alone
does not identify which asset caused an incompatibility.

## Individual recovery versus Restart Rankings

The manager can retry the existing prepared evidence without changing saved
preferences. My DTOS does not initiate provider synchronization, FOIS generation,
historical reconstruction, trade discovery or lineup solving to display the
compatibility review or perform a read-only retry.

When one saved asset needs attention, a separate confirmed action can remove that
exact asset from Custom ordering. It changes only the explicitly selected cohort
membership and its tier boundary. Other assets keep their relative order and
other tier boundaries. Target/Avoid/Protect choices remain saved, including
choices attached to the removed asset. Removing an asset from ordering does not
remove it from the roster, neutral Market, league history or an explicitly
entered trade.

Because the saved cohort changes, remaining current personal price slots can
change. The confirmation explains this consequence. No missing value is replaced
with zero, no alternate player or pick is substituted and no partial curve is
silently published before recovery. Removing the final ranked asset is rejected;
the manager can continue in Neutral mode or deliberately Restart Rankings.

Restart Rankings remains a separate full replacement with the latest compatible
Market order. It requires its existing explicit confirmation, replaces custom
order and tiers, and preserves Target/Avoid/Protect unless the manager separately
chooses to reset those preferences too.

## Identity, ownership and publication

Player IDs and draft-pick year, round and original franchise remain exact.
Current pick ownership is separate from original-franchise identity. A legitimate
ownership transfer does not substitute a different same-year/same-round pick or
silently delete a saved opinion. Protection applies only while the manager
currently owns the exact asset; retaining a Protect preference does not grant
ownership or authority over someone else's roster.

Recovery writes use the existing account/league/controlled-franchise scope,
authenticated session, CSRF and origin protections, current Market generation
and optimistic preference revision. A concurrent edit, revoked session or source
transition rejects a stale command. Read-only views never create preference rows.
The existing bounded document representation and transactional persistence are
reused; no Market price snapshot, migration or permanent analytical store is
introduced.

Custom Trade consumers continue to distinguish personal valuation from neutral
Market fairness and neutral counterparty evidence. An incompatible or unranked
personal asset cannot become a favorable numerical endorsement. Changing
preferences invalidates old personalized results through the existing revision
and source-generation fences. Sleeper projections, legal lineups, strategy
precedence, trade materiality and severe-overpay safeguards are unchanged.

## Validation and acceptance boundaries

Release evidence must exercise the actual disposable account store, HTTP API,
rendered editor and Custom Trade consumers. Controls include normal Market
refresh, newly eligible/removed assets, missing versus zero prices, exact picks,
multiple blockers, confirmed removal, Restart, source transitions, stale revisions
and account isolation. Browser checks cover 320×432, 375×667, 390×844 and desktop,
with keyboard/pointer recovery, visible focus and no horizontal overflow.

The implementer's production acceptance is read-only. If secure account-owned
access is unavailable, the exact live saved asset/revision diagnosis remains
unverified and must be disclosed. Responsive Chromium checks and simulated
manager walkthroughs do not constitute physical iPhone/Safari, unfamiliar-human
or comprehensive screen-reader acceptance. Scout independently reviews the
released implementation and evidence; author-run controls are not independent
acceptance.
