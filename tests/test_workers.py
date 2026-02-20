from unittest.mock import AsyncMock, patch

import aiosqlite

from webhook_receiver.config import Settings
from webhook_receiver.queue import AsyncioEventQueue
from webhook_receiver.store import SQLiteIdempotencyStore
from webhook_receiver.workers import load_pending, process_event

SETTINGS = Settings(max_attempts=3, retry_base_delay=1.0, retry_max_delay=10.0)

REQUEST = {
    "idempotency_key": "evt-001",
    "event_type": "order.created",
    "payload": {"order_id": "ORD-1"},
}


async def _insert(store: SQLiteIdempotencyStore) -> str:
    event, _ = await store.insert_or_get(REQUEST)
    return event.id


@patch("webhook_receiver.workers.asyncio.sleep", new_callable=AsyncMock)
async def test_process_event_marks_completed(mock_sleep, db: aiosqlite.Connection) -> None:
    store = SQLiteIdempotencyStore(db)
    event_id = await _insert(store)
    await process_event(event_id, store, SETTINGS)
    event = await store.get_by_id(event_id)
    assert event.status == "completed"
    assert event.attempts == 0


@patch("webhook_receiver.workers.asyncio.sleep", side_effect=RuntimeError("boom"))
async def test_process_event_retries_on_failure(mock_sleep, db: aiosqlite.Connection) -> None:
    store = SQLiteIdempotencyStore(db)
    event_id = await _insert(store)
    await process_event(event_id, store, SETTINGS)
    event = await store.get_by_id(event_id)
    assert event.status == "pending"
    assert event.attempts == 1
    assert event.retry_after is not None
    assert event.last_error == "boom"


@patch("webhook_receiver.workers.asyncio.sleep", side_effect=RuntimeError("boom"))
async def test_process_event_dead_letters_after_max_attempts(mock_sleep, db: aiosqlite.Connection) -> None:
    store = SQLiteIdempotencyStore(db)
    event_id = await _insert(store)
    for _ in range(SETTINGS.max_attempts):
        await process_event(event_id, store, SETTINGS)
    event = await store.get_by_id(event_id)
    assert event.status == "failed"
    assert event.attempts == SETTINGS.max_attempts


async def test_load_pending_enqueues_ids(db: aiosqlite.Connection) -> None:
    store = SQLiteIdempotencyStore(db)
    event_id = await _insert(store)
    queue = AsyncioEventQueue(maxsize=10)
    await load_pending(queue, store)
    assert queue.qsize() == 1
    assert await queue.get() == event_id
