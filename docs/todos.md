# Design Decisions Backlog

Topics to discuss and turn into ADRs.

## Core Architecture

- [x] **Async processing model** — ADR 0002: in-process asyncio.Queue + N worker coroutines, SQLite as source of truth, EventQueue abstraction for future swap
- [x] **Worker persistence / crash recovery** — folded into ADR 0002: startup loads all pending+processing rows unconditionally, maxsize enforced only on ingestion path
- [x] **Idempotency enforcement** — ADR 0003: UNIQUE constraint on idempotency_key in events table, IdempotencyStore abstraction

## Data Model

- [x] **SQLite schema** — ADR 0004: single events table, UUID PK, status CHECK constraint, attempts+last_error (src/schema.sql)
- [x] **Indexing strategy** — ADR 0004: implicit unique on idempotency_key + composite (status, created_at)
- [ ] **Data retention / TTL** — how to expire old records (background job, SQLite triggers, soft delete)

## API Design

- [ ] **Endpoint design** — POST /webhooks, GET /webhooks/{id} vs. GET /webhooks?idempotency_key=, response shapes
- [ ] **HTTP response on duplicate** — 200, 202, or 409 for re-submitted idempotent events

## Reliability & Concurrency

- [ ] **Concurrency model** — SQLite write serialization, WAL mode, connection pooling
- [ ] **Retry logic for failed processing** — max attempts, backoff, dead-letter state
- [ ] **Graceful shutdown** — how to drain in-flight workers before exit

## Observability

- [ ] **Logging strategy** — structured logs, correlation IDs, log levels
- [ ] **Metrics & health endpoints** — /health, /ready, Prometheus metrics (queue depth, processing latency)

## Rate Limiting

- [ ] **Rate limiting** — per-source IP or API key, in-app vs. reverse proxy

## Deployment

- [ ] **Dockerfile & runtime config** — base image, config via env vars, SQLite file location
