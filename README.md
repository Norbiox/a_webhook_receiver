# webhook-receiver

A prototype webhook receiver service built with FastAPI, asyncio, and SQLite.

## Architecture

Incoming webhooks are persisted to SQLite before any processing begins (inbox pattern), guaranteeing **at-least-once** delivery even if the process crashes mid-flight.

```
POST /webhooks
      │
      ▼
SQLiteIdempotencyStore ──► events table (source of truth)
      │
      ▼ (if new)
AsyncioEventQueue (bounded, in-process)
      │
      ▼
N worker coroutines ──► mark_processing ──► [work] ──► mark_completed / mark_failed
```

**Key components:**

| Module | Responsibility |
|---|---|
| `router.py` | HTTP endpoints, idempotency check, backpressure (429) |
| `store.py` | `SQLiteIdempotencyStore` — all DB access, retry scheduling |
| `workers.py` | `worker` coroutines, `process_event`, startup `load_pending` |
| `cleanup.py` | Background task — hard-deletes expired terminal events |
| `metrics.py` | Prometheus counters/gauges/histograms |
| `config.py` | `Settings` via `pydantic-settings` / env vars |

## Key Tradeoffs

- **At-least-once, not exactly-once** — events may be processed more than once after a crash and restart. Acceptable for a prototype; idempotent downstream handlers are assumed.
- **Single SQLite connection (WAL mode)** — simple and sufficient for the target load (~1000 events/min). Upgrading to Postgres requires replacing `SQLiteIdempotencyStore` only.
- **In-process asyncio queue** — zero infrastructure. Upgrading to Redis Streams requires replacing `AsyncioEventQueue` only (swappable via `EventQueue` Protocol).
- **Bounded queue + 429** — backpressure is enforced at ingestion. Clients must retry on 429.
- **Composite index `(status, created_at)`** — covers startup load, TTL cleanup, and monitoring queries. A leading `created_at` index would be needed if the API gains listing/pagination endpoints.

## Configuration

All settings are read from environment variables:

| Variable | Default | Description |
|---|---|---|
| `DB_PATH` | `/data/events.db` | SQLite file path |
| `WORKER_COUNT` | `10` | Number of worker coroutines |
| `QUEUE_MAXSIZE` | `1000` | In-process queue capacity |
| `MAX_ATTEMPTS` | `5` | Max delivery attempts before dead-lettering |
| `RETRY_BASE_DELAY` | `5.0` | Exponential backoff base (seconds) |
| `RETRY_MAX_DELAY` | `300.0` | Backoff cap (seconds) |
| `RETENTION_DAYS` | `30` | Days to keep completed/failed events |
| `CLEANUP_INTERVAL_HOURS` | `1` | How often the cleanup task runs |
| `LOG_LEVEL` | `INFO` | Python log level |

## Running locally

```bash
uv run uvicorn webhook_receiver.app:create_app --factory --host 0.0.0.0 --port 8000
```

## Running with Docker

```bash
docker build -t webhook-receiver .
docker run -p 8000:8000 -v $(pwd)/data:/data webhook-receiver
```

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/webhooks` | Submit a webhook event |
| `GET` | `/webhooks/{id}` | Get event status by internal ID |
| `GET` | `/webhooks?idempotency_key=` | Get event status by idempotency key |
| `GET` | `/health` | Liveness probe |
| `GET` | `/ready` | Readiness probe (503 until startup load completes) |
| `GET` | `/metrics` | Prometheus metrics |

### POST /webhooks

```json
{ "idempotency_key": "evt-001", "event_type": "order.created", "payload": {} }
```

Returns `202 Accepted` for new events, `200 OK` for duplicates (returns existing status).

## Observability

Prometheus metrics exposed at `/metrics`:

- `webhook_events_total{result}` — ingestion counter (`accepted` / `duplicate` / `rejected`)
- `webhook_queue_depth` — current in-process queue size
- `webhook_processing_duration_seconds` — processing latency histogram
- `webhook_processing_errors_total` — processing error counter

## TODO

- **Rate limiting** — delegate to a reverse proxy (nginx/Traefik); `slowapi` for in-app if needed
- **Trace/correlation IDs** — propagate `X-Request-ID` through logs and responses
- **Exactly-once processing** — requires distributed locking or idempotent downstream consumers
- **Redis Streams** — swap `AsyncioEventQueue` for a Redis-backed implementation to survive restarts with zero in-flight loss
- **OpenTelemetry** — replace plain-text logging with structured traces and spans
- **Pagination** — `GET /webhooks` listing with cursor-based pagination
