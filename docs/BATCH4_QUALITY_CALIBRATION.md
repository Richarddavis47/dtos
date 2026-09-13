# Batch 4 quality calibration — retained-evidence diagnostic

This is not the completed FOIS quality checkpoint or release acceptance.
Production was not accessed or modified. The read-only diagnostic uses
`BATCH4_PRODUCTION_EQUIVALENT_COVERAGE.json` through the active Results scorer.
Run: `.venv/Scripts/python.exe -m tools.validation.audit_fois_retained_quality`.

## Actual available Results outputs

Five completed seasons per manager. These are provisional outputs of the
existing Results methodology, not independently validated final manager grades.

| Manager | Results score | Grade | Metric completeness |
| --- | ---: | --- | ---: |
| RichardDavis47 | 86.52 | B | 80.00% |
| danreilley | 83.16 | B | 80.00% |
| davefedex | 72.49 | C- | 73.33% |
| garrettadame36 | 78.91 | C+ | 73.33% |
| Mears30 | 77.51 | C+ | 80.00% |
| zkobes | 74.66 | C | 80.00% |
| OGV | 48.28 | F | 66.67% |
| TheLandsharks | 76.05 | C | 80.00% |
| anthonyrangel | 67.10 | D+ | 73.33% |
| Markgus13 | 73.84 | C | 73.33% |

The existing scorer reports 100% observed-season confidence for these complete
five-season records. That is not outcome probability or complete FOIS coverage.
Regular-season finishes are absent in this retained adapter output. They are
not reconstructed from postseason finishes. Corrected `worst_finish` to remain
unavailable, matching average/best finish, instead of assigning a favorable 90.

Richard's verified 5 seasons / 4 playoffs / 3 byes / 3 Final Fours / 1 final /
1 title remain unchanged. Scores were not tuned to him. Differences such as
Richard versus dan reflect sustained-season/cycle metrics as well as finals;
championships are not the entire Results score. The large OGV difference is an
existing Results-model output requiring final calibration review, not evidence
of poor decision process. Cycle labels must not be mistaken for inferred intent.

## Category contract and remaining evidence limitation

| Category | Supportable question | Not established by coverage counts |
| --- | --- | --- |
| Results | Observed sustained competitive outcomes | GM decision quality or causal skill |
| Trading process | Actual supported contemporaneous assessment dimensions | Magnitude/direction of those assessments |
| Trading outcome | Independently observed later outcomes | No retained evaluable outcomes in this panel |
| Drafting process | Attribution, slot and activity facts remain available | Timestamp-dependent Market capture; all 370 lack pick times |
| Drafting outcome | Later evidence if independently supportable | No supported retained outcome assessment here |
| Waiver process | Contemporaneous exchange dimensions where present | Direction/magnitude; FAAB counts are not efficiency |
| Waiver outcome | Supported later Market movement at observed horizon | Movement magnitude cannot be recovered from evaluability counts |
| Roster/asset management | Reference coverage and recorded precision | Lineup/depth/strategic quality from reference counts alone |

The cleaned export's retained report contains counts, reasons, confidence
labels, season Results and roster-reference precision, but not per-decision
quality magnitudes or scoped assessment directions. Therefore Trading and
Waiver quality cannot be recalculated from this report. This is a **retained
diagnostic payload limitation**, not absent production evidence or bad manager
performance. Do not rerun against the sparse local Market store and call it
production-equivalent. All ten managers' decision-quality and overall entries
remain unavailable in this diagnostic for that reason.

## Overall and labels

The active aggregation now refuses a single-category overall score. Results
alone remains Results. Existing available-category weighting is otherwise
unchanged: Results 30, Trading 25, Roster 20, Drafting 15, Waivers 10; supported
categories are renormalized by their included weight when configuration permits.
This guard is necessary, not proof that every two-category combination supports
a final overall grade. Final decision-quality calibration remains open.

Unavailable dimensions never become zero or automatic improvement areas.
Strengths and constraints in this diagnostic come only from Results evidence;
no Trading/Drafting/Waiver strengths are inferred from activity or coverage.

## Pick and release status

Preserve Day Traders 120 picks / 4 rounds and Super Flexxxin 90 / 3, ownership
reconciliation, explicit generic quotes, original-franchise identity and UNKNOWN
ranges. Remaining range/confidence, portfolio history and complete switch parity
are pending. No completed Pick Market boundary was reopened.

No new durable canonical payloads, production export, backfill, comprehensive
gate or release was performed. Bounded-storage proof remains unchanged.
Batch 4 is incomplete; Batch 5 has not started.
