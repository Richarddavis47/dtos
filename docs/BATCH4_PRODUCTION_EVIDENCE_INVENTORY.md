# Batch 4 bounded production evidence inventory

Read-only SQLite (`mode=ro`) and retained Sleeper gzip reads. No imports of
mutating history services, no backfill, source copy, production write or release.
Global Market counts are shared observations, not league-specific decisions.

| Season | Global historical player Market | Retained pick observations | Day Traders rosters | Draft selections | Completed trades | Completed waiver/free-agent records | FAAB present / real zero |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 2021 | 61 | 10 | 10 | 250 | 32 | 252 | 75 / 35 |
| 2022 | 142 | 35 | 10 | 30 | 97 | 401 | 74 / 28 |
| 2023 | 82 | 33 | 10 | 30 | 39 | 257 | 33 / 12 |
| 2024 | 93 | 42 | 10 | 30 | 41 | 266 | 49 / 19 |
| 2025 | 44 | 36 | 10 | 30 | 22 | 290 | 16 / 5 |
| 2026 | 1,535 live player observations | 0 global | archive absent | not inventoried | not inventoried | not inventoried | not inventoried |

All 422 historical player observations and 156 historical pick observations
have zoned ISO timestamps. The pick observations are the previously classified
synthetic range averages: PRESENT BUT INCOMPATIBLE with generic Market grading,
not 156 legitimate generic quotes. Preserve originals; exclude from grading.

2026 player observations: 600 zoned ISO, 935 invalid or unzoned timestamps.
These 935 are not eligible for precise as-of selection. The candidate's canonical
selector now parses actual instants, rejects missing timezone/event-label dates,
and compares timezone-equivalent instants correctly. Twenty-one focused tests
pass. Production observations were not altered.

## Day Traders checkpoint references

| Season | Player checkpoints / linked global observation | Pick checkpoints / linked global observation |
| --- | --- | --- |
| 2021 | 78 / 76 | 56 / 20 |
| 2022 | 287 / 287 | 142 / 76 |
| 2023 | 68 / 67 | 80 / 35 |
| 2024 | 91 / 90 | 90 / 51 |
| 2025 | 53 / 53 | 56 / 34 |
| 2026 | 204 / 198 | 31 / 0 |

Reference counts do not equal independent observations or evaluable decisions.
Historical player Market: AVAILABLE/PARTIAL, previously disconnected by numeric
player ID lookup, corrected in candidate. Historical player production/usage
coverage is not established by these Market counts and remains to inventory.

Roster records: AVAILABLE reconstruction anchors, not proof of complete as-of
rosters. Transfer replay and boundary completeness still require validation.
Transactions and selections: AVAILABLE source identity/activity. Every completed
trade/waiver record has a source created/status-updated field (284, 498, 296,
307, 312 respectively); timestamp presence is not precision validation. Exact
selection timestamps/intervals still require canonical boundary inspection.

Waiver adds/drops per season: 231/233, 301/306, 182/217, 201/202, 201/225.
FAAB: PARTIAL; absent bids are not zero and may be inapplicable to free agents.
Drafting/Waiver quality: NOT YET FULLY CONSUMED BY EVALUATOR, not a source absence.
No final evaluability upper bound or manager quality grade is claimed from
aggregate inventory. Production-equivalent evaluator application remains open.
