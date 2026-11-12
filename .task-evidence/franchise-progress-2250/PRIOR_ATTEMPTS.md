# Earlier attempts — original outcomes remain distinct

The initial stage seal remains byte-for-byte in earlier-stage-original.zip.
Its statement that no application gate had failed applied only to that earlier
seal time. It does not describe later full-local or cancelled hosted validation.

The first f40 full local run failed the existing FOIS heartbeat assertion:
542.770149 ms against an unchanged 500 ms limit. It had no OOM/admission deferral.
Its already-failed remainder was deliberately interrupted. 1,840 stop events are
not a passing-test count: six gates passed, unit regression failed, and three
subsequent gates did not execute. The entire original failed archive, console,
events, memory, manifest and recorded cancellation are retained here.

The diagnostic replay ran the same 1,211 preceding methods and two real worker
operations. Both completed two records (114.12/78.62 ms heartbeat maxima).
An explicit collection between them found 940,075 unreachable objects and took
1.806 seconds. The original stall did not reproduce; its exact cause remains
unproven. The final fixture collects old garbage before creating/timing its own
50,000-player workload. GC stays enabled; admission, worker and 500 ms limit are
unchanged, with explicit two-record completion assertions added. Diagnostic
passes are never substituted for final full regression.

Two earlier diagnostic prototypes were unusable: the first failed before tests
on a nested-AST instrumentation lookup; the second was cancelled for extra held
TestCase references and missing discover-observer activation. The second owned
disposable container needed a stop after graceful interruption did not finish.
Neither establishes application cancellation/cleanup behavior. Original methods,
logs and limitations remain separate.

The f40 hosted canonical was cancelled by the new source head, with 3,828 starts
and 3,827 stops. Its result/trace/manifest were not finalized. All twelve other
required f40 jobs passed, but their results are not final b522-source evidence.
The cancelled original ZIP is retained separately at an immutable evidence Git
commit, with its API SHA256 and Actions artifact identity; original console/events are included here without alteration.

The first b522 supplemental 103-method focused run had one failure/five errors:
the earlier browser-only external runner lacked __main__ protection. A spawned
worker imported it, repeated root.mkdir(), raised FileExistsError and broke the
pool. This harness defect was corrected without application changes; originals
are retained and the corrected complete focused run is separate.

Read original publisher fixture failures and dirty-source development boundaries
in earlier-stage-readable/PRIOR_ATTEMPTS.md. No failed source/log is recreated.
Private fixture databases, raw cache contents, private API envelopes, credentials
and reusable delivery URLs are excluded. Finite cleanup is not leak-freedom proof.
