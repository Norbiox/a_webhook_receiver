# 7. Configuration via Environment Variables

## Status

Accepted

## Context

Operational parameters (`RETENTION_DAYS`, `CLEANUP_INTERVAL_HOURS`, `WORKER_COUNT`, queue `maxsize`, etc.) must be tunable without code changes, and visible in container deployments.

## Decision

All configurable parameters are read from environment variables with sensible defaults. No config files.

## Consequences

- Works out of the box with Docker and container orchestrators.
- Defaults are chosen so the service runs without any configuration required.
- No secrets management needed at this stage — the service has no external credentials.
