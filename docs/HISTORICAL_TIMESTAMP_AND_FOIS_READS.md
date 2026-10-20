# Historical timestamp selection and FOIS history reads

The historical Market lookup selects by validated timezone-aware quote instants,
after admitting both quote and source-knowledge clocks against the decision
cutoff. Fractional precision and equivalent timezone offsets do not change
chronology. Equal instants use the immutable observation ID as a deterministic
tie-break, not retrieval time or a claim of superior provenance. Exact asset and
Market context constrain the query. Candidate rows stream through the existing
index without a text-ordered truncation; only the best admitted row is retained.
No schema, retained-date rewrite, provider normalization or migration is needed.

FOIS profile history reads retained score observations. They do not acquire
Sleeper sources, replay league transactions, prepare canonical generations or
recompute process/outcome grades. The retained semantic-state decoder recursively
validates compressed full/delta roots, hashes, lengths, dependency depth and
league/model/tenure scope. Repeated observations can reference identical roots.

Each timeline call now owns a memo limited to eight verified roots and 8 MiB of
serialized bytes. It reuses the exact bytes already validated by the decoder;
each result parses its own nested evidence and applies its own observation
metadata. Root misses still execute the unchanged recursive validation. Oversize
roots are not retained. No cache survives the call or crosses leagues/accounts.
No long SQLite read transaction or write lock is introduced: publication can
commit while the memo exists. A subsequent call starts empty and revalidates the
new source. No FOIS scores, evidence qualifications or storage formats change.

Existing request-correlated spans now distinguish history SQL fetch, state
decoding, current-score classification and league rankings. They are nested in
the existing profile history span; do not add inclusive times as independent
costs. Fixed names and existing bounded diagnostics are used, without payloads,
new endpoints, synchronous sampling, storage or provider calls.

Disposable representative profiling demonstrates repeated work and verifies
byte-identical retained databases and equal decoded output. It is not proof of
the exact production cost split or resolution of the historical OOM, original
44.230-second cold Home gap, background-worker contention, or 500 ms production
liveness under a large profile request. Independent Scout acceptance is required.
Retained historical grades remain RETAINED / NOT REVALIDATED.
