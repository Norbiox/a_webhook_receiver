# 6. SQLite Concurrency Model

## Status

Accepted

## Context

The service runs multiple concurrent asyncio coroutines — API handlers inserting events, N workers updating status, and a cleanup task deleting expired rows — all sharing a single SQLite database. SQLite's default concurrency model would serialize all access and block readers during writes.

## Decision

Enable **WAL mode** on startup:

```sql
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;
```

Use **aiosqlite** for all database access to avoid blocking the event loop. A **single shared connection** is sufficient — aiosqlite serializes operations through one internal worker thread, matching SQLite's single-writer constraint without additional coordination.

### WAL mode — pros and cons

**Pros:**
- Readers and writers do not block each other — status check API calls proceed while workers update rows
- Writes are atomic and durable — a crash mid-write does not corrupt the database
- Better write throughput under concurrent read load compared to default journal mode

**Cons:**
- WAL introduces a second file (`events.db-wal`) that must be present alongside the database file — relevant for backup and volume mount configuration
- WAL is not suitable for databases on network filesystems (NFS, SMB) — not a concern here since SQLite is always local
- Checkpoint operations (flushing WAL to main DB file) add occasional write spikes — manageable with `PRAGMA wal_autocheckpoint` if needed

`busy_timeout=5000` instructs SQLite to retry for up to 5 seconds on lock contention before raising an error, rather than failing immediately.

## Alternatives

**Default journal mode (DELETE)**
Simpler, no extra files. Writers lock the entire database, blocking all readers. Unacceptable for concurrent API + worker access.

**Connection pool (multiple connections)**
Would allow more parallelism in theory, but SQLite still serializes writes — multiple connections only help if reads dominate. Adds coordination complexity. The single aiosqlite connection is sufficient at target scale.

## Consequences

- Concurrent reads and writes are supported without blocking each other.
- The `events.db-wal` file must be included in any backup or volume snapshot alongside `events.db`.
- All database access goes through a single `aiosqlite` connection shared across the application lifetime.
