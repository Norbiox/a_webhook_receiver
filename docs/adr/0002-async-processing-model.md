# 2. Async Processing Model

## Status

Accepted

## Context

The service must accept webhooks quickly (fast HTTP response) and process them asynchronously. Processing must survive service restarts — no event can be lost.

SQLite is the required persistence layer. No external broker is available in the prototype.

## Decision

Use an **in-process asyncio.Queue** as the delivery mechanism between the API and worker coroutines, with **SQLite as the source of truth**.

Flow:
1. **Startup** — before the service signals readiness, load IDs of all `pending` and `processing` events from SQLite into the queue.
2. **Ingestion** — on POST, write the event to SQLite with status `pending`, then enqueue the ID. Return immediately.
3. **Processing** — N worker coroutines consume IDs from the queue, mark the row `processing` in SQLite, do the work, then mark `completed` or `failed`.
4. **Backpressure** — the queue has a configured `maxsize` (configurable via env). If full, the POST handler returns `429 Too Many Requests`. The `maxsize` is enforced only on the ingestion path — startup load is unbounded, so crash recovery always completes fully regardless of queue cap.

Status lifecycle:
```
pending → processing → completed | failed
```

The queue is accessed via a thin `EventQueue` abstraction (Protocol), so the backing implementation can be swapped (e.g. Redis Streams) without changing API or worker logic.

## Alternatives

**Separate worker process polling SQLite**
Decoupled lifecycle, but adds operational complexity (two processes to manage). SQLite still limits to a single writer, so no scaling benefit. Polling introduces latency between event arrival and processing start. Rejected for the prototype; viable as an intermediate step before a real queue.

**Task queue library (ARQ / Celery) + Redis**
Clean, battle-tested, handles retry and scheduling well. Requires Redis as additional infrastructure, too much for the prototype. The `EventQueue` abstraction makes this a future upgrade path without redesign.

## Consequences

- **Crash recovery** is inherent: SQLite rows with status `pending` or `processing` are re-enqueued on next startup.
- **At-least-once processing**: an event picked from the queue but not yet marked `completed` will be re-queued on restart. Workers and downstream handlers must tolerate occasional reprocessing.
- **Horizontal scaling** is not supported in this design — multiple instances would duplicate the in-memory queue. The upgrade path is to replace `asyncio.Queue` with Redis Streams or a similar persistent queue and SQLite with Postgres.
- **Throughput** is tunable via the number of worker coroutines (`WORKER_COUNT` env var).
- **Backpressure** is surfaced to callers via 429; external systems are expected to retry with backoff.
