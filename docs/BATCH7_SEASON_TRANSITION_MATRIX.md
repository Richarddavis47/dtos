# Batch 7 focused season-transition matrix

This matrix records only states established by retained Sleeper league settings,
prepared matchup evidence and the canonical projection publication contract. A
wall-clock guess is not promoted into league state.

| Source state | Trigger | Expected canonical state | Prepared/cache effect | Durable-write effect | Recovery expectation |
| --- | --- | --- | --- | --- | --- |
| Preseason or pre-week (`leg=1`, `last_scored_leg=0`) | First valid source publication | Week 1 is pregame; actual zero placeholders are not completed evidence | League/season/scoring-compatible projection generation only | One semantic publication; unchanged replay writes nothing new | Missing source stays unavailable; a later valid source repairs it |
| Active regular-season week (`leg=n`, `last_scored_leg=n-1`) | Current source changes | Current week remains active/pregame or in-progress from score evidence | Atomic replacement of the compatible generation | Only changed source/player/generation identities are added | Failed preparation leaves the last valid generation readable |
| Completed regular-season week | `last_scored_leg` advances | Prior week becomes historical/final; current week remains separate | Prepared matchup generation changes; historical reads do not consume current projections | Existing historical facts remain append-oriented; no rewrite of prior season facts | Restart restores only an exactly compatible projection head |
| Regular-season rollover | `leg` advances before playoff start | Next configured week becomes current; earlier weeks are historical | Old week head is incompatible with the new current week | New semantic head only; unchanged sources deduplicate | Old week is never attached as the new current week |
| Playoff qualification boundary | Regular season completes and bracket evidence is available | Qualification/byes come only from canonical bracket evidence | Brackets are prepared after the configured regular season | Bounded prepared/cache replacement; no projected qualification fact | Missing bracket remains unavailable rather than projected/locked |
| Playoff round transition | All configured component weeks of the prior round complete | Next-round identities may resolve from bracket dependencies | New prepared matchup generation; opponent remains unlocked before dependency completion | One semantic transition | Partial bracket/source preserves an unresolved state |
| Multi-week playoff continuation | First component finishes, later component incomplete | Round remains unresolved; component scores remain distinct | Same configured round and every component week retained | No final-round fact until every component completes | Restart reconstructs the same unresolved round |
| Season complete (`status=complete`, `leg=last_scored_leg`) | Final configured round completes | Completed season is readable as historical evidence | No current projection may be substituted into historical views | Existing source/history retained; identical replay deduplicates | Restart preserves final facts without reprocessing a transition |
| Offseason / next-season boundary | Global NFL clock and connected league season differ | Selected league season remains authoritative for its projection scope | Wrong-season projection is rejected; absence stays unavailable | No cross-season cache attachment or duplicate source universe | The proper new league/season publication establishes the new head |
| Next-season projection/cache rollover | League season/week/scoring identity changes | Only exact league + season + week + scoring evidence is compatible | Prior head stays durable history but is not restored into active state | New semantic publication; prior facts are not rewritten | Corrupt/incompatible disposable head fails closed and can be rebuilt |

Day Traders and Super Flexxxin are exercised through separate league identities,
scoring profiles, lineup structures and playoff calendars. The matrix does not
encode either league's constants. Normal reads consume prepared evidence and do
not initiate projection ingestion, FOIS grading, trade search, pick construction
or report persistence.
