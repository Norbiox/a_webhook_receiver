# 3. Idempotency Enforcement

## Status

Accepted

## Context

The same webhook can be delivered multiple times by external systems (retries, at-least-once delivery guarantees on the sender side). The service must process each logical event exactly once, identified by `idempotency_key`.

## Decision

Enforce idempotency via a `UNIQUE` constraint on `idempotency_key` in the `events` table. No separate dedup table or external lock is used.

On ingestion:
1. Attempt `INSERT` of the new event.
2. If the insert succeeds — event is new, enqueue for processing.
3. If it raises a unique constraint violation — event is a duplicate, fetch and return the existing record.

Idempotency logic is encapsulated behind an `IdempotencyStore` abstraction:

```python
class IdempotencyStore(Protocol):
    async def insert_or_get(self, event: Event) -> tuple[Event, bool]:
        ...
        # returns (event, is_new)
```

Today backed by SQLite unique constraint. Future implementations could use Redis `SET NX` or Postgres `INSERT ... ON CONFLICT DO NOTHING`.

## Alternatives

**Separate `idempotency_keys` table**
Decouples dedup from event storage. Adds complexity with no benefit at this scale — the key and the event always move together.

**Application-level check (SELECT then INSERT)**
Check existence before inserting. Introduces a race condition under concurrent requests — two identical webhooks arriving simultaneously could both pass the check and both insert. Rejected in favor of the atomic DB constraint.

**Redis `SET NX`**
Atomic, fast, purpose-built for this. Requires Redis infrastructure. The `IdempotencyStore` abstraction makes this a drop-in future upgrade.

## Consequences

- Duplicate detection is atomic and race-condition-free at the DB level.
- No additional infrastructure required.
- The `IdempotencyStore` abstraction isolates the implementation, making it swappable without touching API or worker logic.
