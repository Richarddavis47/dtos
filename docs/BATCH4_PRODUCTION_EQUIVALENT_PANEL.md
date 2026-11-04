# Batch 4 — production-equivalent Day Traders coverage

Candidate evaluation ran locally against an authorized, sanitized production
export. No candidate code ran on Render. Production SQLite used `mode=ro` and
`query_only`; only temporary files under `/tmp` were written.

Export SHA256: `0c932283c7bef5e69d48d46b11fcdcc23bc95c36a7723d4596114068d9afd7fc`.
Size: 807,936 bytes. Five season archives, 1,536 relevant global Market rows,
1,237 league checkpoints and 1,237 league references. The companion JSON
contains source archive hashes, sanitized hashes, generation and season groups.
This is retained-source parity for the specified evaluation inputs, not a claim
to reproduce every live production service or current operational state.

## Decision coverage

E/P/I = evaluable / partially evaluable / insufficient. Trading counts are
manager participations, not distinct league trades. These are coverage states,
not quality grades. Trading legacy confidence is not reported; scoped Waiver
assessments/outcomes report `limited_scope`, otherwise `unavailable`.

| Manager | Trades | Trading process E/P/I | Draft selections (all process/outcome I) | Waivers | Waiver process E/P/I | Waiver outcome E/P/I | FAAB known / zero / missing |
|---|---:|---|---:|---:|---|---|---|
| RichardDavis47 | 82 | 4/73/5 | 38 | 168 | 0/7/161 | 0/10/158 | 26/17/142 |
| danreilley | 63 | 6/50/7 | 34 | 252 | 0/10/242 | 0/16/236 | 28/9/224 |
| davefedex | 116 | 6/102/8 | 42 | 264 | 0/16/248 | 0/20/244 | 56/22/208 |
| garrettadame36 | 25 | 1/23/1 | 35 | 157 | 0/3/154 | 0/7/150 | 40/12/117 |
| Mears30 | 28 | 2/22/4 | 48 | 146 | 0/1/145 | 0/10/136 | 28/12/118 |
| zkobes | 18 | 2/15/1 | 33 | 56 | 0/5/51 | 0/5/51 | 12/3/44 |
| OGV | 75 | 4/71/0 | 25 | 159 | 0/21/138 | 0/20/139 | 11/5/148 |
| TheLandsharks | 16 | 1/13/2 | 42 | 118 | 0/6/112 | 0/7/111 | 20/7/98 |
| anthonyrangel | 9 | 1/7/1 | 45 | 40 | 0/0/40 | 0/0/40 | 5/1/35 |
| Markgus13 | 32 | 2/29/1 | 28 | 106 | 0/2/104 | 0/5/101 | 21/11/85 |

All Trading outcomes are insufficient in this active run. Explicit-zero FAAB
is a subset of known, not an additional category. No activity count is a grade.
All ten managers have five supported completed Results seasons; see
`BATCH4_REAL_RESULTS_PANEL.md` for qualification/byes/Final Four/finals/titles.
Richard remains 5 completed / 4 playoffs / 3 byes / 3 Final Fours / 1 final / 1 title.
Grouping preserves owner-by-season; exact intra-season tenure timing is unproven.

## Historical roster context

| Manager | Decision references | Complete / partial ownership | Transaction boundary / pre-draft anchor |
|---|---:|---|---|
| RichardDavis47 | 181 | 156/25 | 168/13 |
| danreilley | 261 | 250/11 | 252/9 |
| davefedex | 281 | 260/21 | 264/17 |
| garrettadame36 | 167 | 145/22 | 157/10 |
| Mears30 | 169 | 134/35 | 146/23 |
| zkobes | 64 | 56/8 | 56/8 |
| OGV | 159 | 158/1 | 159/0 |
| TheLandsharks | 135 | 115/20 | 118/17 |
| anthonyrangel | 60 | 37/23 | 40/20 |
| Markgus13 | 109 | 104/5 | 106/3 |

Boundary is the requested reconstruction time, not proof of exact ownership.
Ownership availability remains separately reported. Context supports identity
and inventory evidence, not a demonstrated roster-fit/strategy assessment.
Standalone Roster Construction/Asset Management quality is not yet evaluated.

## Limitations exposed by the actual panel

- Trading: 387 incomplete Market packages, 304 incomplete historical-context
  classifications, six missing package identities (reasons can overlap).
- Drafting: all 370 selections lack an exact accepted decision timestamp in
  the current evaluator. Its resulting `NO_CONTEMPORANEOUS_MARKET` reason is
  therefore NOT proof that production lacks historical Market observations.
  Conservative interval-based evaluation remains an evaluator limitation.
  No supported alternative-quality assessment was emitted.
- Waivers: 934 actions have no contemporaneous Market evidence; 1,395 lack
  complete comparable add/drop Market coverage; 1,219 lack applicable known
  FAAB. All 1,466 lack a supported roster-fit conclusion despite retained
  roster references. The latter is an assessment limitation, not missing anchors.
- Later Market changes are partial observations, not full realized NFL outcomes.

## Comparison and calibration readiness

The earlier local store contained only eight September 2026 observations.
Production-equivalent Trading and Waiver coverage is materially higher; the
earlier zero-recovery result must not be reused as production coverage.

Coverage is now measured, but not yet sufficient to declare final quality
calibration complete: draft interval handling, roster-fit assessment and
Trading outcome limitations need narrow classification. No championship-only
overall grade or missing-evidence penalty was manufactured. No comprehensive
gates were run. Batch 5 remains unstarted.

## Access cleanup

Remote helper/export were removed and absence checked. Render reported no
authorized SSH keys; a fresh SSH attempt returned public-key denial. Both the
previous revoked local key and this transfer's key pair were removed. No
public endpoint, service, paid resources or production schema changes occurred.
