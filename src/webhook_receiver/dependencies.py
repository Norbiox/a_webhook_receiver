from functools import lru_cache

import aiosqlite
from fastapi import Depends, Request

from webhook_receiver.config import Settings
from webhook_receiver.queue import AsyncioEventQueue
from webhook_receiver.store import SQLiteIdempotencyStore


@lru_cache
def get_settings() -> Settings:
    return Settings()


async def get_db(request: Request) -> aiosqlite.Connection:
    return request.app.state.db


async def get_store(
    db: aiosqlite.Connection = Depends(get_db),
) -> SQLiteIdempotencyStore:
    return SQLiteIdempotencyStore(db)


async def get_queue(request: Request) -> AsyncioEventQueue:
    return request.app.state.queue
