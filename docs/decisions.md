# Decisions

All architectural and design decisions in one place.

---

## Architecture

**Pattern:** Inbox Pattern — `events` table is the inbox, every webhook persisted before processing.

**Async processing:** In-process `asyncio.Queue` as delivery mechanism, SQLite as source of truth. Queue accessed via `EventQueue` Protocol (swappable).

**Processing guarantee:** At-least-once. Workers must be idempotent.

**Startup sequence:** Before signalling readiness, load all `pending` and `processing` rows into the queue (unbounded, no maxsize enforced at startup).

**Graceful shutdown:** Not implemented. On SIGTERM, in-flight workers are interrupted. Events mid-processing are re-enqueued on next startup.

**Workers:** N coroutines configured via `WORKER_COUNT` env var.

**Backpressure:** Queue has configurable `maxsize`. When full, POST returns `429 Too Many Requests`.

---

## Idempotency

**Mechanism:** `UNIQUE` constraint on `idempotency_key` in `events` table. Encapsulated in `IdempotencyStore` Protocol (DB-only, no cache).

**On new event:** `INSERT` succeeds → enqueue.

**On duplicate:** `INSERT` raises unique violation → `SELECT` existing row → return current status.

---

## Data Model

**Schema:** Single `events` table. See `src/schema.sql`.

| Column | Type | Notes |
|---|---|---|
| `id` | `TEXT` | UUID primary key |
| `idempotency_key` | `TEXT` | UNIQUE |
| `event_type` | `TEXT` | |
| `payload` | `TEXT` | JSON blob |
| `status` | `TEXT` | CHECK: `pending\|processing\|completed\|failed` |
| `attempts` | `INTEGER` | default 0 |
| `last_error` | `TEXT` | nullable |
| `retry_after` | `TEXT` | ISO8601, NULL = eligible immediately |
| `created_at` | `TEXT` | ISO8601 |
| `updated_at` | `TEXT` | ISO8601 |

**Status lifecycle:** `pending → processing → completed | failed`

**Indexes:**
- Implicit UNIQUE on `idempotency_key`
- `idx_events_status_created_at` on `(status, created_at)` — covers startup load, TTL cleanup, status monitoring

**Known limitation:** queries without a `status` filter (e.g. last N events by `created_at`) do a full table scan.

---

## Retry Logic

**On failure:** increment `attempts`, record `last_error`.

**If `attempts < MAX_ATTEMPTS`:** reset to `pending`, set `retry_after = now + backoff`, re-enqueue.

**If `attempts >= MAX_ATTEMPTS`:** leave as `failed` (dead-letter). No further retries.

**Backoff:** `min(RETRY_BASE_DELAY * 2^attempts, RETRY_MAX_DELAY)`

**Startup loader query:**
```sql
WHERE status IN ('pending', 'processing')
AND (retry_after IS NULL OR retry_after <= ?)
```

---

## Data Retention

**Cleanup:** Periodic background asyncio task, interval `CLEANUP_INTERVAL_HOURS` (default `1h`).

**Retention period:** `RETENTION_DAYS` (default `30`).

**Eligible for deletion:** only `completed` and `failed` rows. `pending` and `processing` rows are never deleted.

**Method:** Hard delete in batches of 1000 rows, repeated until no rows remain.

```sql
DELETE FROM events WHERE id IN (
    SELECT id FROM events
    WHERE status IN ('completed', 'failed') AND created_at < ?
    LIMIT 1000
)
```

---

## SQLite / Concurrency

**Mode:** WAL (`PRAGMA journal_mode=WAL`)

**Timeout:** `PRAGMA busy_timeout=5000`

**Connection:** Single shared `aiosqlite` connection for the application lifetime.

**Backup note:** `events.db-wal` must be included alongside `events.db` in any backup or volume snapshot.

---

## API

| Endpoint | Method | Description |
|---|---|---|
| `/webhooks` | `POST` | Submit a webhook |
| `/webhooks/{id}` | `GET` | Get event status by internal ID |
| `/webhooks?idempotency_key=` | `GET` | Get event status by idempotency key |
| `/health` | `GET` | Liveness check |
| `/ready` | `GET` | Readiness check (not ready until startup queue load completes) |

**POST response (new event):** `202 Accepted` — fields: `id`, `idempotency_key`, `status`, `created_at`

**POST response (duplicate):** `200 OK` — same shape, current status

**GET status response fields:** `id`, `idempotency_key`, `status`, `created_at`, `updated_at`

---

## Observability

**Logs:** Plain text (prototype). No correlation IDs. **TODO (production):** structured JSON, OpenTelemetry for correlated traces + metrics + logs, `X-Request-ID` header support.

**Log levels:** ingestion `INFO`, duplicate detected `INFO`, processing start `INFO`, processing complete `INFO`, retry scheduled `INFO`, failure `ERROR`.

**Metrics:** Prometheus endpoint exposed — queue depth, processing latency, ingestion rate, error rate.

---

## Configuration

All parameters via environment variables with sensible defaults. No config files.

| Variable | Default | Description |
|---|---|---|
| `WORKER_COUNT` | — | Number of async worker coroutines |
| `QUEUE_MAXSIZE` | — | Max in-memory queue size (backpressure threshold) |
| `MAX_ATTEMPTS` | `5` | Max processing attempts before dead-letter |
| `RETRY_BASE_DELAY` | `5s` | Exponential backoff base |
| `RETRY_MAX_DELAY` | `300s` | Exponential backoff cap |
| `RETENTION_DAYS` | `30` | Event TTL |
| `CLEANUP_INTERVAL_HOURS` | `1` | Cleanup task interval |
| `DB_PATH` | `/data/events.db` | SQLite file location |
| `LOG_LEVEL` | — | Log verbosity |
| `LOG_FORMAT` | — | `json` or `pretty` |

---

## Rate Limiting

Not implemented. **TODO:** delegate to reverse proxy (nginx, Traefik).

---

## Deployment

- **Base image:** `python:3.14-alpine`
- **Port:** `8000` (hardcoded)
- **DB path:** configurable via `DB_PATH`, default `/data/events.db`, `/data` is a volume mount
- **User:** non-root `appuser`

---

## Technical Standards

- **Language / framework:** Python 3.14, FastAPI
- **Testing:** pytest, TDD approach
- **Linting / formatting:** Ruff
- **Type annotations:** everywhere
- **Style:** functions ≤ 15 lines, DRY, KISS, SOLID
