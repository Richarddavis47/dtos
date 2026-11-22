# Build 2274 recovery

PR #363 remains the release vehicle. The current source is 3ffc907fd2340100afb762b133a5533fe0ad52dc, tree 137d5aa04f710a36bcf1bb54008d0f915ab880fc. The only change from the first candidate is browser teardown between independent viewport journeys in one existing regression test. Main and production remain build 2273.

- Source checkout /workspace/dtos-ir-2274-isolation-control and controller /workspace/2274-bye-pickup-ir-final. First candidate checkout /workspace/dtos-draft-capital-2247 and controller /workspace/2274-bye-pickup-ir preserve its separate history.
- Original local runner finishes on its own source. start-after-original.sh waits for its actual exit and schedules focused and full local validation of the successor. The unchanged 2 GiB canonical runner writes canonical-invocation.json, its exit, raw logs and verification receipts.
- Final hosted runs are 44976057308, 44976057325, 44976057296 and 44976057284. watch-hosted.sh verifies completion and builds the exact archive download queue. The first hosted failure and the controlled isolation comparison are under prior-attempts.
- after-local.py awaits the final local pass before the supplemental resource and visual checks. Preserve only actual passing evidence for the final source. Never report a failed or missing gate as passed.
- Finish the standing visual review and verification of original hosted receipts. Build the immutable evidence archives, run prepare-publisher.sh, independently verify the prepare receipt, update PR evidence and use merge-and-dispatch.sh only after every gate passes. Verify immutable release and live readiness, then publish original consoles, checksums, and the final Scout handoff.
