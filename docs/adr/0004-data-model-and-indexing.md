# 4. Data Model and Indexing

## Status

Accepted

## Context

The service needs to persist webhook events durably, enforce idempotency, support crash recovery on startup, enforce TTL-based retention, and expose event status to callers. SQLite is the required storage engine.

## Decision

Single `events` table (see `src/schema.sql`). Key design choices:

- **`id` as UUID text** — portable to Postgres without schema changes, avoids coupling to SQLite's integer rowid
- **`idempotency_key UNIQUE`** — atomic duplicate detection at the DB level (see ADR 0003)
- **`status` with CHECK constraint** — enforces the lifecycle `pending → processing → completed | failed` at the DB level
- **`attempts` + `last_error`** — tracks retry history without a separate table; cheap to add now, required for retry logic
- **`created_at` / `updated_at` as ISO8601 text** — SQLite has no native datetime type; ISO8601 strings sort correctly lexicographically

**Indexes:**

| Index | Columns | Serves |
|---|---|---|
| (implicit) | `idempotency_key` | duplicate detection on INSERT |
| `idx_events_status_created_at` | `(status, created_at)` | startup load, TTL cleanup, status monitoring |

The composite `(status, created_at)` index covers all critical query patterns via the leftmost prefix rule:
- `WHERE status IN ('pending', 'processing') ORDER BY created_at` — startup load, FIFO ordering
- `WHERE status IN ('completed', 'failed') AND created_at < ?` — TTL cleanup
- `WHERE status = ?` — monitoring queries

TTL cleanup is intentionally scoped to terminal statuses (`completed`, `failed`). Active events (`pending`, `processing`) are never deleted by the cleanup job regardless of age.

## Alternatives

**Separate `idempotency_keys` table** — rejected, see ADR 0003.

**`(status, created_at)` + standalone `idx_events_created_at`** — the standalone index would additionally serve unfiltered `ORDER BY created_at` queries. Rejected to avoid the extra write overhead on every status update; the tradeoff is documented as a known limitation below.

**Integer primary key** — simpler, slightly faster for SQLite. Rejected because UUIDs are portable across storage backends and fit the planned upgrade path.

## Consequences

- Every status transition (`pending → processing`, etc.) updates the composite index — 2–3 index writes per event lifetime. Acceptable at target scale (1000 events/min).
- **Known limitation:** queries without a `status` filter (e.g. "last 10 events by created_at") cannot use the composite index and will do a full table scan. These are monitoring/debug queries, not on the critical path. Add a standalone `idx_events_created_at` if this becomes a bottleneck.
- **Known limitation:** `status` has low cardinality (4 values). SQLite's query planner handles this well at moderate scale; at very high row counts, query hints or partial indexes may be needed.
