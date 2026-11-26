# Scout acceptance for the phone-first League page

These paired Chromium screenshots use identical disposable prepared data in the baseline and candidate. The parity extracts came from actual League routes and the shared matchup reader. They cover every displayed rank, franchise name, record, Points For, Points Against, supported streak and projected matchup score. The receipts show what was evaluated under a real 2 GiB limit. Older failed layout and preflight attempts remain separate. No screenshot uses private account data.

1. In a prepared fixture or an already activated owner league, open League at 320 px, 390 px and desktop. Verify that all teams fit without horizontal scrolling, long names wrap, and the signed-in franchise has a “You” marker. Check rank, record, Points For and streak against the same prepared source. Open standings evidence for Points Against, champion evidence, placement qualifications and provenance.
2. Verify the actual Sleeper playoff count. Confirm the line follows that number of rows. In a division or customized format, treat the line as the number of spots and follow View playoff race for qualification. Confirm a missing count explains the limit and omits the line.
3. Check that a supported changed rank has an arrow, a signed value and an accessible direction. Compare an explicit unchanged 0 with the unavailable dash. A completed head-to-head streak is separate from rank change and median games. Try a first-week or incomplete publication and verify that unavailable rank history is not shown as zero.
4. Change the matchup preview week with the arrow, keeping the standings reporting week fixed. Review projected points, live scores or completed final scores as supported. Follow View matchup and All matchups. Use contextual Back to recover the original selected week. Check the recap, Transactions, Draft Capital, History and specialist tools.
5. Switch to a separately prepared league. Reconcile its roster count, playoff count, format, selected franchise and accounts without changing production preferences. Navigate by keyboard and touch, and check for clipped cells or controls with sticky navigation present.

Candidate commit c910a3a4c7c97a63c400ec80cc8f604cc421d6fb, tree 353feba0c022a750229e748a04ebdab43eac71da. Baseline v1.22.65 / build 2280. This fixture evidence supports responsive Chromium acceptance. Signed-in owner production and physical iPhone Safari require separate verification.

## Release hold reconciliation

All 4,683 local tests and all ten canonical gates passed on the exact candidate under the enforced 2 GiB limit. Peak was 2,010,091,520 bytes and no OOM was recorded. All 13 required hosted jobs passed on the same tree. The full local acceptance used the intact pinned validation image with enough physical disk. Both original local failures remain separately preserved. No application or safety threshold changed during recovery.

For an independent spot check, inspect the failing first Trade case from the original logs, then check the matching run in the recovered console. All 17 actual Trade admissions passed in that case with the original 402,653,184-byte requirement. The diagnostics distinguish readiness probes from actual admissions. Review the earlier disk and admission attempts as receipts, not passing gates.

[Original local logs, comparison and checksum manifest](https://github.com/Richarddavis47/dtos/tree/f58a4e676da18be2ce97f2abb905d96897313927/.task-evidence/league-redesign-2281/candidate-c910a3a/local-gate-recovery)

[Hosted canonical run, attempt 2](https://github.com/Richarddavis47/dtos/actions/runs/45681099959/attempts/2)

## Released source and independent checks

Verify readiness reports v1.22.66 / build 2281 and merge 4a58ab3e83fb49de6e81518298691c99fdb8ff7d. The deployed tree is 353feba0c022a750229e748a04ebdab43eac71da, the validated candidate tree. All 23 release attachments are immutable and checksum-verified. Independent production checks passed on readiness, the public Welcome page and three demos, authenticated endpoint denial for unauthenticated requests, and byte equality for the served League, Market and Trade assets.

Use a prepared 10-team and 12-team disposable league for independent rendering. The phone fixtures cover 320, 375 and 390 pixels plus desktop at 1280 pixels. The 320px narrow layout can wrap shortcut labels and franchise names. Use the live viewport to confirm all actions remain reachable. The full-page stitched image places fixed bottom navigation at the viewport boundary. Live owner standings, account switching and physical iPhone Safari remain untested. If an already prepared authorized league is available, compare the reporting week, records, PF, streak, prior-week movement and playoff count to prepared evidence. Change the Matchups week and use Back while keeping the standings reporting week fixed. Keep acceptance read-only.

[Immutable release](https://github.com/Richarddavis47/dtos/releases/tag/v1.22.66)

[Original local runs and resumable diagnostic evidence](https://github.com/Richarddavis47/dtos/tree/f58a4e676da18be2ce97f2abb905d96897313927/.task-evidence/league-redesign-2281/candidate-c910a3a/local-gate-recovery)

[Before/after Chromium scenes, original focused logs and matched prepared data](https://github.com/Richarddavis47/dtos/tree/a5fbdb1e0e80e7ebfa8909293d4330456f22d89c/.task-evidence/league-redesign-2281/candidate-c910a3a)

[Guarded publication original](https://github.com/Richarddavis47/dtos/actions/runs/45730534976)
