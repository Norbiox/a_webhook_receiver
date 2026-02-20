import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from webhook_receiver.cleanup import cleanup_task
from webhook_receiver.config import Settings
from webhook_receiver.database import open_db
from webhook_receiver.dependencies import get_settings
from webhook_receiver.logging_setup import configure_logging
from webhook_receiver.queue import AsyncioEventQueue
from webhook_receiver.router import router
from webhook_receiver.store import SQLiteIdempotencyStore
from webhook_receiver.workers import load_pending, worker


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level)
        app.state.ready = False
        app.state.db = await open_db(settings.db_path)
        app.state.queue = AsyncioEventQueue(maxsize=settings.queue_maxsize)
        store = SQLiteIdempotencyStore(app.state.db)
        await load_pending(app.state.queue, store)
        tasks = [asyncio.create_task(worker(app.state.queue, store, settings)) for _ in range(settings.worker_count)]
        tasks.append(asyncio.create_task(cleanup_task(store, settings)))
        app.state.ready = True
        yield
        for task in tasks:
            task.cancel()
        await app.state.db.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(router)
    return app
