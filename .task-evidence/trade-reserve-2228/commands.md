# Original commands and evidence scope

Production baseline: public GET /health/ready and git origin/main, no league entry/search.

Source fixtures (Python 3.14.3, UID 1000, actual 2 GiB/no swap, two CPUs, no network):
- python run-constrained.py /evidence/probe.py (initial missing sys.path setup failed; attempt 2 retained).
- python run-constrained.py -m unittest tests.test_trade_lineup_detail tests.test_reserve_quality -v (36 passed).
- python run-constrained.py -m unittest tests.test_trade_reserve_evidence -v (13 attempted, one Superflex failure exposed irrelevant-position candidate issue).
- python run-constrained.py -m unittest tests.test_trade_reserve_evidence tests.test_trade_lineup_detail tests.test_reserve_quality tests.test_multileague_projection_compatibility -v (62 passed before final additional controls).
- python run-constrained.py -m unittest tests.test_trade_reserve_evidence tests.test_trade_lineup_detail tests.test_reserve_quality tests.test_multileague_projection_compatibility tests.test_reserve_quality_admission tests.test_reserve_quality_consumers -v (77 passed).
- DTOS_LINEUP_DETAIL_EVIDENCE=/evidence/browser python run-constrained.py -m unittest tests.test_trade_lineup_detail_browser -v (first attempt formatting assertion failed at four sizes and subsequent artifact directory missing; corrected test expectation, second attempt two tests passed, all sizes).
- DTOS_RESOURCE_SOURCE=<exact worktree> python run-constrained.py /evidence/capture.py <baseline-capture|candidate-capture> (10 samples/case, same projection generation; baseline checkout commit 40cea169 has exactly production tree).
- DTOS_EXPECTED_HEAD=<candidate> DTOS_RESOURCE_SOURCE=<exact worktree> python run-constrained.py -m tools.validation.restoration_preflight_gate --output /evidence/local-preflight (five genuine enforced-container admission cases).

Final full validation uses run-clean.py -> unchanged original canonical runner -> python -m tools.validation.validate_release, clean exact-commit writable checkout, UID1000, 2 GiB/no swap, two CPUs, network none. Original complete console, observer, ten-gate trace, memory records, hashes and manifest retained. Its actual outcome is reported only in result.json/local-verified.json once complete.

Publisher uses the established isolated Actions branch and native GITHUB_TOKEN contents:write, with separate prepare and post-merge publish operations. No direct Cloud asset upload, credential change or infrastructure modification.
