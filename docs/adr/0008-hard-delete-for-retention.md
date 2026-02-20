# 8. Hard Delete for Data Retention

## Status

Accepted

## Context

Expired events must be removed to bound storage growth. Two common approaches are hard delete (remove rows) and soft delete (mark rows as deleted, filter everywhere).

## Decision

Use hard `DELETE` for expired events. Soft delete is rejected.

## Alternatives

**Soft delete (`deleted_at` / `is_deleted` flag)**
Preserves history but rows still consume space — which is the problem being solved. Requires filtering deleted rows in every query. No benefit for this use case.

## Consequences

- Expired event data is permanently unrecoverable after deletion.
- No schema or query complexity added.
- If audit history is required in the future, an append-only event log or archival export should be introduced before enabling retention.
