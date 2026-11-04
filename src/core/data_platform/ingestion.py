"""Bounded background/CLI ingestion, resumable at atomically committed batches."""
from __future__ import annotations

from itertools import islice
from typing import Callable, Iterable

from .global_evidence import GlobalEvidenceStore, GlobalFact, IngestionCheckpoint


def ingest(store: GlobalEvidenceStore, *, key: str, source_identity: str,
           facts: Callable[[], Iterable[GlobalFact]], retrieved_at: str,
           batch_size: int = 250) -> dict[str, int | bool]:
    """Run off the request path; caller pins an immutable source revision.

    Source iteration is bounded by a batch plus one lookahead record. Failed
    batches never advance the durable cursor. No lock spans provider I/O.
    """
    if not 1 <= batch_size <= 1000:
        raise ValueError("Invalid ingestion batch size.")
    checkpoint = store.ingestion_checkpoint(key)
    same = checkpoint is not None and checkpoint["source_identity"] == source_identity
    if same and checkpoint["complete"]:
        return {"created": 0, "reused": 0, "resumed_at": checkpoint["offset"], "complete": True}
    offset = checkpoint["offset"] if same else 0
    resumed = offset
    created = reused = 0
    iterator = iter(facts())
    try:
        skipped = sum(1 for _ in islice(iterator, offset))
        if skipped != offset:
            raise ValueError("Pinned source became shorter than its committed checkpoint.")
        pending = next(iterator, None)
        if offset and pending is None:
            raise ValueError("Pinned source lost the record following its incomplete checkpoint.")
        while pending is not None:
            batch = [pending, *islice(iterator, batch_size - 1)]
            pending = next(iterator, None)
            result = store.publish(batch, retrieved_at=retrieved_at,
                checkpoint=IngestionCheckpoint(key, source_identity, offset, offset + len(batch), pending is None))
            offset += len(batch)
            created += result["created"]
            reused += result["reused"]
        if offset == 0:
            store.publish([], retrieved_at=retrieved_at,
                          checkpoint=IngestionCheckpoint(key, source_identity, 0, 0, True))
    finally:
        close = getattr(iterator, "close", None)
        if close:
            close()
    return {"created": created, "reused": reused, "resumed_at": resumed, "complete": True}
