import asyncio
import logging
from datetime import UTC, datetime, timedelta

from webhook_receiver.config import Settings
from webhook_receiver.store import SQLiteIdempotencyStore

logger = logging.getLogger(__name__)


async def cleanup_task(store: SQLiteIdempotencyStore, settings: Settings) -> None:
    while True:
        cutoff = datetime.now(UTC) - timedelta(days=settings.retention_days)
        before = cutoff.isoformat()
        deleted = await store.delete_expired(before)
        if deleted:
            logger.info("Cleanup deleted %d expired events", deleted)
        await asyncio.sleep(settings.cleanup_interval_hours * 3600)
