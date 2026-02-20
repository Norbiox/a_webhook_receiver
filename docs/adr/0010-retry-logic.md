# 10. Retry Logic for Failed Processing

## Status

Accepted

## Context

Processing a webhook can fail (e.g. unexpected error during simulation). Failed events must be retried automatically up to a configurable limit, with backoff to avoid hammering a recovering system.

## Decision

On processing failure:
1. Increment `attempts`, record `last_error`.
2. If `attempts < MAX_ATTEMPTS` — reset status to `pending`, set `retry_after = now + backoff(attempts)`, re-enqueue.
3. If `attempts >= MAX_ATTEMPTS` — leave as `failed`. No further retries.

**Backoff formula** — exponential with a cap:
```
delay = min(RETRY_BASE_DELAY * 2^attempts, RETRY_MAX_DELAY)
```

Both configurable via env vars (`RETRY_BASE_DELAY` default `5s`, `RETRY_MAX_DELAY` default `300s`, `MAX_ATTEMPTS` default `5`).

**`retry_after`** is stored in SQLite (ISO8601). The startup loader and any future polling mechanism skip rows where `retry_after > now`, so backoff survives restarts.

**Dead-letter** — after `MAX_ATTEMPTS`, the event remains `failed`. No separate status is introduced; dead-letter events are queryable via `status = 'failed' AND attempts >= MAX_ATTEMPTS`.

## Alternatives

**Fixed delay between retries**
Simpler but risks overwhelming a recovering system. Exponential backoff is the standard and adds minimal complexity.

**Separate `dead_letter` status**
Cleaner operationally but adds a status value and branching logic. The `failed` + `attempts` combination is sufficient for the prototype.

**In-process asyncio.sleep before re-enqueue**
Simple but delay is lost on restart — event would be re-enqueued immediately after recovery. `retry_after` in DB is restart-safe.

## Consequences

- Failed events are retried automatically without operator intervention.
- Backoff delay survives service restarts.
- `retry_after` column added to `events` table (see `src/schema.sql`).
- Startup loader query updated to exclude events not yet eligible: `WHERE status IN ('pending', 'processing') AND (retry_after IS NULL OR retry_after <= ?)`.
- Dead-letter events accumulate as `failed` rows until TTL cleanup removes them (ADR 0005).
