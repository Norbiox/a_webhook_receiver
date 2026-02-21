# Design Decisions Backlog

Topics to discuss and turn into ADRs.

## Core Architecture

- [x] **Async processing model** — ADR 0002: in-process asyncio.Queue + N worker coroutines, SQLite as source of truth, EventQueue abstraction for future swap
- [x] **Worker persistence / crash recovery** — folded into ADR 0002: startup loads all pending+processing rows unconditionally, maxsize enforced only on ingestion path
- [x] **Idempotency enforcement** — ADR 0003: UNIQUE constraint on idempotency_key in events table, IdempotencyStore abstraction

## Data Model

- [x] **SQLite schema** — ADR 0004: single events table, UUID PK, status CHECK constraint, attempts+last_error (src/schema.sql)
- [x] **Indexing strategy** — ADR 0004: implicit unique on idempotency_key + composite (status, created_at)
- [x] **Data retention / TTL** — ADR 0005: periodic background asyncio task, batched hard delete of terminal events, configurable via RETENTION_DAYS + CLEANUP_INTERVAL_HOURS

## API Design

- [X] **Endpoint design** — POST /webhooks, GET /webhooks/{id} vs. GET /webhooks?idempotency_key=, response shapes
- [X] **HTTP response on duplicate** — 200, 202, or 409 for re-submitted idempotent events

## Reliability & Concurrency

- [x] **Concurrency model** — ADR 0006: WAL mode + busy_timeout, single aiosqlite connection
- [x] **Retry logic for failed processing** — ADR 0010: exponential backoff, retry_after in DB, MAX_ATTEMPTS configurable, failed = dead-letter
- [x] **Graceful shutdown** — noted in ADR 0002: cut immediately on SIGTERM, restart recovery handles in-flight events

## Observability

- [X] **Logging strategy** — structured logs, correlation IDs, log levels
- [X] **Metrics & health endpoints** — /health, /ready, Prometheus metrics (queue depth, processing latency)

## Rate Limiting

- [X] **Rate limiting** — per-source IP or API key, in-app vs. reverse proxy

## Deployment

- [X] **Dockerfile & runtime config** — base image, config via env vars, SQLite file location
