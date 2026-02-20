CREATE TABLE IF NOT EXISTS events (
    id              TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    event_type      TEXT NOT NULL,
    payload         TEXT NOT NULL,           -- JSON blob
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    retry_after     TEXT,                    -- ISO8601, NULL means eligible immediately
    created_at      TEXT NOT NULL,           -- ISO8601
    updated_at      TEXT NOT NULL            -- ISO8601
);

-- Serves: startup load (WHERE status IN ('pending', 'processing') ORDER BY created_at)
-- Serves: TTL cleanup (WHERE status IN ('completed', 'failed') AND created_at < ?)
-- Serves: status-only monitoring queries (WHERE status = ?)
CREATE INDEX IF NOT EXISTS idx_events_status_created_at ON events (status, created_at);
