# 9. In-Memory Idempotency Cache

## Status

Accepted

## Context

ADR 0003 enforces idempotency via a UNIQUE constraint on `idempotency_key`. Handling a duplicate still requires hitting the DB — a failed INSERT followed by a SELECT. At high ingestion rates with frequent retries, this adds unnecessary DB load.

Duplicates are assumed to arrive shortly after the original (seconds to minutes — typical retry behavior).

## Decision

Maintain a bounded **LRU cache** of recently seen `idempotency_key` values in memory. On ingestion:

1. Check the LRU cache first.
2. If found → fetch status from DB and return immediately (no INSERT attempt).
3. If not found → proceed with INSERT as per ADR 0003; on success or unique violation, add the key to the cache.

The cache is populated on startup from existing DB rows.

Cache size is configurable via `IDEMPOTENCY_CACHE_SIZE` (default `10_000`).

The `IdempotencyStore` abstraction (ADR 0003) wraps both layers — callers are unaware of the cache.

## Alternatives

**Unbounded cache (all known keys)**
Guarantees a cache hit for any duplicate regardless of age. Rejected — unbounded memory growth (~1.4M keys/day at target scale).

**No cache**
Every request hits the DB. Correct but wasteful for the common duplicate pattern.

## Consequences

- DB load from duplicate submissions is minimized for the common case (recent retries).
- A cache miss (evicted or post-restart key) falls through to the DB — correctness is preserved, the UNIQUE constraint remains the source of truth.
- Cache is per-instance and not shared — acceptable since horizontal scaling is out of scope (ADR 0002).
