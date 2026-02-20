# 5. Data Retention / TTL

## Status

Accepted

## Context

Events accumulate in SQLite indefinitely without a cleanup mechanism. At ~1000 events/minute, that is ~1.4M rows/day. A retention policy is required to bound storage growth.

## Decision

A **periodic background asyncio task** runs at a configurable interval (`CLEANUP_INTERVAL_HOURS`, default `1`) and deletes expired terminal events in batches.

Retention period is configurable via `RETENTION_DAYS` (default `30`).

**Only terminal events are eligible for deletion** — `pending` and `processing` rows are never deleted regardless of age, as they represent work that must still be completed.

Deletion runs in batches to avoid long SQLite write locks:

```sql
DELETE FROM events WHERE id IN (
    SELECT id FROM events
    WHERE status IN ('completed', 'failed') AND created_at < ?
    LIMIT 1000
)
```

The loop repeats until no rows are deleted.

The `(status, created_at)` composite index (ADR 0004) covers this query efficiently.

## Alternatives

**Soft delete (`is_deleted` flag)**
Preserves history but rows still consume space and require filtering everywhere. No benefit for this use case. Rejected.

**SQLite triggers on INSERT**
Could auto-expire old rows on each insert. Fragile, hard to observe, and couples retention logic to the write path. Rejected.

**Delete all qualifying rows in one statement**
Simpler but risks a long write lock on SQLite when many rows expire at once (e.g. after a retention period change or first cleanup run). Batching keeps lock durations short and predictable.

**Startup-only cleanup**
Misses long-running instances. Rejected in favor of periodic execution.

## Consequences

- Storage is bounded; growth rate is predictable (`RETENTION_DAYS × ~1.4M rows/day` upper bound).
- Cleanup runs in-process — no extra infrastructure needed.
- Long-lived `processing` rows (e.g. stuck events) are never deleted and will accumulate. Monitoring for stale `processing` rows is recommended (see observability ADR).
- A change to `RETENTION_DAYS` takes effect on the next cleanup run without a restart.
