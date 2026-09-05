# Bounded restart evidence deduplication

Production v1.13.3 completed 1,038 capture requests but exceeded its 500,000-node
guard with 503,868 nodes. It retained a failure journal, produced no complete
snapshot, and did not restart. OOM and kill counters stayed zero. The previously
unclassified v1.13.2 restart is not assigned a cause by this diagnostic failure.

Category counts included 358,239 semantic-record nodes, 52,685 confidence-input
nodes, 51,179 market-row nodes and 30,608 projection nodes. Normalized provider
rows occurred both in `semantic_records[].valuation.providers[]` and in the
confidence section. The latter now retains only the distinct raw normalization
inputs. No unique canonical field is omitted.

Schema v3 preserves exact allowlisted safe numerical confidence and freshness
values at the canonical provider location. Other private identifiers and unknown
values remain fingerprinted and fully compared. The fixed path is matched exactly;
it does not broaden public serialization to arbitrary confidence-named fields.
Cross-schema comparison fails explicitly. Use fresh v3 pre/post captures.

The 500,000-node and 64 MiB guards are unchanged. The expanded sanitized fixture
contains 1,500 players plus canonical picks, populated Brain and valuation data.
It proves the duplicate layout fails the same node guard while the deduplicated
complete layout fits. No product model, artifact semantics, provider behavior,
account boundary, infrastructure setting or production data is modified.
