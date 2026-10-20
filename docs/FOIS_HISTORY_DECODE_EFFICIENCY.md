# Verified retained-history decoding

The HTML GM profile needs each historical observation's date, score and grade,
not a resident copy of every nested decision. `timeline_summary` still decodes
and verifies every row and constructs its normal score DTO for schema and
retained-evidence qualification. It immediately projects that DTO to an
immutable small summary. It does not prune history, skip required states or
change the full timeline/profile APIs. Current-snapshot classification and exact
observation metadata use the same boundary as full reads.

Delta bases are freshly deserialized, privately owned JSON trees. Only this
internal reader uses owned delta application. The general delta API still copies
its arguments. Scope identities are captured before mutation and checked after
application; dependency cycle/depth, decompression, serialized byte count, SHA
identity and league validation remain mandatory. The already constructed JSON
tree need not be copied and reparsed after canonical verification. Nested unknown
fields, missing/null/zero, transaction and pick identity are not transformed.

The existing eight-root/8 MiB serialized-byte LRU is unchanged. It lasts for one
read, returns independent evidence trees and does not hold a write-blocking read
transaction. There is no cross-request history cache, source call, schema,
permanent summary record or grade regeneration. Full-evidence API reads can still
have substantial transient memory costs; no universal capacity claim is made.

Author-run disposable Python 3.14.3 containers enforce a real 2 GiB limit and
compare one unchanged database (three leagues, 1,251 observations / 99 states).
Full output hashes and summary projections must match. Memory profiling is
bounded to the smaller 49-row league: the initial large full-history tracemalloc
collector exceeded its cgroup and is retained as failed diagnostic evidence.
Streaming equality hashes avoid collector-owned full-history copies. Cold means
first process read, not a flushed filesystem or guaranteed production cold start.

Browser orphan probes compare container PID1 Python with Docker's init reaper;
this is validation-environment diagnosis, not a production process-manager change.
Concurrent read fixtures overlap actual isolated prepare/idempotent publication,
not FOIS grade computation. Production traces and fixture measurements must stay
separate. The historical OOM and original cold Home gap remain unresolved.
