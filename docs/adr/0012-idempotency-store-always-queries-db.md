# 12. IdempotencyStore Always Queries the Database

## Status

Accepted. Supersedes ADR 0009.

## Context

ADR 0009 proposed an in-memory LRU cache to short-circuit DB queries for duplicate webhooks. However, the API contract requires returning the **current processing status** of a duplicate event — not just whether it exists. Since status changes over time (`pending → processing → completed / failed`), a key-only cache would always be stale and a DB query is unavoidable.

## Decision

The `IdempotencyStore` always queries the database. No in-memory cache layer is used.

On ingestion:
1. Attempt `INSERT` of the new event.
2. If the insert succeeds → event is new, enqueue for processing.
3. If a unique constraint violation occurs → event is a duplicate, `SELECT` the existing row and return its current status.

The `IdempotencyStore` abstraction (ADR 0003) is retained — the implementation is simply DB-only.

## Alternatives

**Cache `(key → status)` and keep it updated**
Workers would need to update the cache on every status transition. Complex, error-prone, and the DB is already fast enough for this access pattern with the UNIQUE index. Rejected.

## Consequences

- Every duplicate submission hits the DB — one failed INSERT + one SELECT.
- The UNIQUE index on `idempotency_key` makes both operations fast.
- Callers always receive the current, accurate status for duplicate submissions.
