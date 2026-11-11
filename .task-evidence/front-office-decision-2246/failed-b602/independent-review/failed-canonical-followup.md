The exact b602 hosted canonical run **failed**. Run `42991843827`, attempt 1,
job `130426505856`, tested `b602d6acd03cc1c95d85ee734d2d7f28658885cf`
(tree `8a687ea0256d6e0031b57e08e2a1a38a90a1a535`). Its sole failure among 4364 completed tests
was the fixture worker's `release.wait(2.0)` assertion at
`tests/test_projection_audit.py:302`, propagated at the audit await on line 328.
The **under 100 ms assertion on line 333 was never reached**.

Original `unittest-console.log:24775–24776` records `/lightweight` returning 200
and a 2.712-second event-loop turn in this test. The recorded traceback reaches
`asyncio.to_thread`, then the patched fixture builder. The source places explicit
`gc.collect()` after that worker starts, inside its two-second held deadline.
This is a concrete fixture ordering problem. The originals do not measure that
GC call independently, so the full 2.712 seconds cannot be attributed to GC.

The minimum safe correction is to move the existing setup collection and comment
immediately before `asyncio.create_task()` on line 310. Preserve enabled GC,
the 2.0-second worker wait,250 ms request timeout,under 100 ms assertion,
worker-start/pending checks and all response/context assertions. A second
read-only reviewer found no flaw in that relocation. No production logic or
memory/admission change is supported by this failure.

Five original samples during the 2.723-second case show raw cgroup usage
`1,173,331,968–1,173,340,160` bytes of `2,147,483,648`, at least
`974,143,488` bytes (~929 MiB) sampled raw headroom, with zero max/OOM events.
These are sequential interval samples, not an exact GC measurement. The
full-suite peak `2,122,092,544` bytes is not the failed case's headroom.
The runner was not timed out, reaped its validator and exited 1; the container was
not OOM-killed. Six initial gates passed, the unit/regression gate failed and
three later canonical gates did not execute. Artifact integrity is separately
recorded and cannot change the failed outcome.

Recommendation only: no source edits, tests, Docker, network or MCP calls were
made by this reviewer. The running local suite was untouched. Preserve these
failed originals and obtain fresh required validation on any corrected exact
source; a focused pass cannot replace the complete canonical gate. Detailed
original references, sampled values and limits are in
`failed-canonical-followup.json`.
