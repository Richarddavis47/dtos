# Scout acceptance for the phone-first League page

These paired Chromium screenshots use identical disposable prepared data in the baseline and candidate. The parity extracts came from actual League routes and the shared matchup reader. They cover every displayed rank, franchise name, record, Points For, Points Against, supported streak and projected matchup score. The receipts show what was evaluated under a real 2 GiB limit. Older failed layout and preflight attempts remain separate. No screenshot uses private account data.

1. In a prepared fixture or an already activated owner league, open League at 320 px, 390 px and desktop. Verify that all teams fit without horizontal scrolling, long names wrap, and the signed-in franchise has a “You” marker. Check rank, record, Points For and streak against the same prepared source. Open standings evidence for Points Against, champion evidence, placement qualifications and provenance.
2. Verify the actual Sleeper playoff count. Confirm the line follows that number of rows. In a division or customized format, treat the line as the number of spots and follow View playoff race for qualification. Confirm a missing count explains the limit and omits the line.
3. Check that a supported changed rank has an arrow, a signed value and an accessible direction. Compare an explicit unchanged 0 with the unavailable dash. A completed head-to-head streak is separate from rank change and median games. Try a first-week or incomplete publication and verify that unavailable rank history is not shown as zero.
4. Change the matchup preview week with the arrow, keeping the standings reporting week fixed. Review projected points, live scores or completed final scores as supported. Follow View matchup and All matchups. Use contextual Back to recover the original selected week. Check the recap, Transactions, Draft Capital, History and specialist tools.
5. Switch to a separately prepared league. Reconcile its roster count, playoff count, format, selected franchise and accounts without changing production preferences. Navigate by keyboard and touch, and check for clipped cells or controls with sticky navigation present.

Candidate commit c910a3a4c7c97a63c400ec80cc8f604cc421d6fb, tree 353feba0c022a750229e748a04ebdab43eac71da. Baseline v1.22.65 / build 2280. This fixture evidence supports responsive Chromium acceptance. Signed-in owner production and physical iPhone Safari require separate verification.

## Review boundary

PR #370 remains a draft. Production is still v1.22.65 / build 2280. The exact v1.22.66 candidate passed responsive League fixtures, the standalone unmodified HTTP worker, and all 13 required hosted jobs. The successful hosted canonical archive includes 4,683 tests and all ten gates under the enforced 2 GiB limit.

The first local canonical attempt completed 4,683 tests with two failures and three errors. The second attempt on unchanged source completed 4,683 tests with three failures and eight errors. The original console, process receipt, and per-request admission evidence identify capacity deferrals in the affected Trade journeys under the unchanged limit. The second run recorded 13 such observations in failing cases and zero OOM kills. The cause of the hosted/local discrepancy remains unresolved. A passing full local result is still required. Guarded publishing and production owner acceptance remain pending.

- [Paired 320, 390 and 1280 px screenshots and matched prepared values](https://github.com/Richarddavis47/dtos/tree/a5fbdb1e0e80e7ebfa8909293d4330456f22d89c/.task-evidence/league-redesign-2281/candidate-c910a3a)
- [Passing hosted canonical attempt and original artifact](https://github.com/Richarddavis47/dtos/actions/runs/45681099959/attempts/2)
- [PR source and release state](https://github.com/Richarddavis47/dtos/pull/370)

The enclosed ZIP preserves original console and timing bytes from both local attempts. Open the separate result records with SHA256SUMS. This review is based on Chromium fixtures. Signed-in owner production and physical iPhone Safari are unverified.
