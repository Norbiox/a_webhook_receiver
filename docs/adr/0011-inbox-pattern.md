# 11. Inbox Pattern

## Status

Accepted

## Context

External systems deliver webhooks with at-least-once guarantees — the same event may arrive multiple times. The service must deduplicate and process each event exactly once, and must not lose events under failures.

## Decision

The `events` table serves as an **inbox** — every incoming webhook is persisted before any processing begins. The `idempotency_key` uniquely identifies each logical event within the inbox.

Mapping to the pattern:

| Inbox Pattern concept | This service |
|---|---|
| Inbox store | `events` table |
| Message identifier | `idempotency_key` (UNIQUE constraint) |
| Duplicate detection | Failed INSERT → return existing record (ADR 0003) |
| Async processing | Worker coroutines consuming from `asyncio.Queue` (ADR 0002) |
| Processing state | `status` column: `pending → processing → completed / failed` |

The inbox is the single source of truth. No event is processed unless it exists in the inbox, and no event is accepted twice.

## Consequences

- Decouples ingestion from processing — the inbox absorbs spikes while workers process at their own pace.
- Crash recovery is inherent — the inbox persists across restarts, pending entries are re-queued on startup (ADR 0002).
- The pattern is implemented across ADR 0002 (async processing), ADR 0003 (idempotency), ADR 0004 (schema), but named here for clarity.
