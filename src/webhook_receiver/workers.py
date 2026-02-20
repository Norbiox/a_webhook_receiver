import asyncio
import logging
import random
import time
from datetime import UTC, datetime

from webhook_receiver.config import Settings
from webhook_receiver.metrics import (
    PROCESSING_DURATION,
    PROCESSING_ERRORS_TOTAL,
    QUEUE_DEPTH,
)
from webhook_receiver.queue import EventQueue
from webhook_receiver.store import SQLiteIdempotencyStore

logger = logging.getLogger(__name__)


async def process_event(event_id: str, store: SQLiteIdempotencyStore, settings: Settings) -> None:
    logger.info("Processing event %s", event_id)
    await store.mark_processing(event_id)
    start = time.monotonic()
    try:
        await asyncio.sleep(random.uniform(2, 5))
        await store.mark_completed(event_id)
        logger.info("Completed event %s", event_id)
    except Exception as e:
        PROCESSING_ERRORS_TOTAL.inc()
        await store.mark_failed(
            event_id,
            str(e),
            settings.max_attempts,
            settings.retry_base_delay,
            settings.retry_max_delay,
        )
        event = await store.get_by_id(event_id)
        if event.status == "failed":
            logger.error("Dead-letter event %s error=%s", event_id, e)
        else:
            logger.info("Retry scheduled event %s attempts=%s", event_id, event.attempts)
    finally:
        PROCESSING_DURATION.observe(time.monotonic() - start)


async def worker(queue: EventQueue, store: SQLiteIdempotencyStore, settings: Settings) -> None:
    while True:
        event_id = await queue.get()
        QUEUE_DEPTH.set(queue.qsize())
        await process_event(event_id, store, settings)


async def load_pending(queue: EventQueue, store: SQLiteIdempotencyStore) -> None:
    now = datetime.now(UTC).isoformat()
    for event_id in await store.get_pending_ids(now):
        await queue.put(event_id)
