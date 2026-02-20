import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest

from webhook_receiver.cleanup import cleanup_task
from webhook_receiver.config import Settings
from webhook_receiver.store import SQLiteIdempotencyStore

SETTINGS = Settings(retention_days=30, cleanup_interval_hours=1)


async def _insert(store: SQLiteIdempotencyStore, key: str, status: str, days_old: int) -> None:
    created_at = (datetime.now(UTC) - timedelta(days=days_old)).isoformat()
    await store._conn.execute(
        "INSERT INTO events(id,idempotency_key,event_type,payload,status,"
        "attempts,last_error,retry_after,created_at,updated_at) "
        "VALUES(?,?,?,'{}',?,0,NULL,NULL,?,?)",
        (key, key, "test", status, created_at, created_at),
    )
    await store._conn.commit()


async def test_delete_expired_removes_old_terminal_events(
    db: aiosqlite.Connection,
) -> None:
    store = SQLiteIdempotencyStore(db)
    await _insert(store, "old-completed", "completed", days_old=31)
    await _insert(store, "old-failed", "failed", days_old=31)
    before = datetime.now(UTC).isoformat()
    deleted = await store.delete_expired(before)
    assert deleted == 2


async def test_delete_expired_keeps_recent_events(db: aiosqlite.Connection) -> None:
    store = SQLiteIdempotencyStore(db)
    await _insert(store, "recent", "completed", days_old=5)
    before = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    deleted = await store.delete_expired(before)
    assert deleted == 0


async def test_delete_expired_keeps_active_events(db: aiosqlite.Connection) -> None:
    store = SQLiteIdempotencyStore(db)
    await _insert(store, "old-pending", "pending", days_old=60)
    await _insert(store, "old-processing", "processing", days_old=60)
    before = datetime.now(UTC).isoformat()
    deleted = await store.delete_expired(before)
    assert deleted == 0


@patch("webhook_receiver.cleanup.asyncio.sleep", new_callable=AsyncMock)
async def test_cleanup_task_runs_and_logs(mock_sleep, db: aiosqlite.Connection) -> None:
    store = SQLiteIdempotencyStore(db)
    await _insert(store, "old", "completed", days_old=31)
    mock_sleep.side_effect = [None, asyncio.CancelledError()]
    with pytest.raises(asyncio.CancelledError):
        await cleanup_task(store, SETTINGS)
    mock_sleep.assert_called_with(SETTINGS.cleanup_interval_hours * 3600)
