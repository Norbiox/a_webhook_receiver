# CLAUDE.md

## Project

Webhook receiver prototype — focus on architecture and design, not production hardening.

- Requirements: `docs/requirements.md`
- All decisions compiled: `docs/decisions.md`
- ADRs: `docs/adr/*.md` (template in `docs/adr/template.md`)

## Tech stack

Python 3.14, FastAPI, aiosqlite, pydantic-settings, prometheus-client, uvicorn.
Tools: uv, ruff, pytest + pytest-cov, pre-commit — see `mise.toml` / `pyproject.toml`.

## Key architecture decisions

- **Inbox pattern** — every webhook persisted before processing (ADR 0011)
- **At-least-once** — not exactly-once; idempotent downstream assumed (ADR 0002)
- **asyncio.Queue** — in-process delivery, bounded, 429 on full (ADR 0002)
- **Single aiosqlite connection, WAL mode** (ADR 0006)
- **IdempotencyStore always queries DB** — no cache; status must be current (ADR 0012)
- **Composite index `(status, created_at)`** — covers worker startup load + TTL cleanup (ADR 0004)
- **Hard delete** of terminal events only (`completed`/`failed`) after retention window (ADR 0008)
- **Exponential backoff** with `retry_after` stored in DB — restart-safe (ADR 0010)

## Source layout

```
src/webhook_receiver/
  config.py       Settings (env vars, pydantic-settings)
  database.py     open_db() — WAL + schema init from schema.sql
  models.py       WebhookRequest / WebhookResponse / EventStatusResponse
  store.py        SQLiteIdempotencyStore — all DB access
  queue.py        EventQueue Protocol + AsyncioEventQueue
  workers.py      process_event / worker / load_pending
  cleanup.py      cleanup_task — periodic hard delete
  metrics.py      Prometheus counters/gauges/histograms
  router.py       All HTTP endpoints
  app.py          create_app() + lifespan wiring
  dependencies.py FastAPI DI: get_settings / get_db / get_store / get_queue
```

## Testing

```bash
uv run pytest          # runs with --cov, branch=true, fail-under=90
uv run ruff check .
uv run ruff format .
```

Tests bypass lifespan via `dependency_overrides[get_db/get_queue]` — see `tests/conftest.py`.

## Code standards

- Type annotations everywhere
- Functions ≤ 15 lines
- Ruff rules: E, F, I, UP, B (B008 ignored — FastAPI Depends in defaults is intentional)
- 90% branch + line coverage enforced via pre-commit
