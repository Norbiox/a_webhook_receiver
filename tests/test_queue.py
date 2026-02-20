import asyncio

import pytest

from webhook_receiver.queue import AsyncioEventQueue


async def test_put_and_get() -> None:
    q = AsyncioEventQueue(maxsize=10)
    await q.put("evt-001")
    assert await q.get() == "evt-001"


async def test_qsize() -> None:
    q = AsyncioEventQueue(maxsize=10)
    await q.put("evt-001")
    await q.put("evt-002")
    assert q.qsize() == 2


async def test_full() -> None:
    q = AsyncioEventQueue(maxsize=1)
    await q.put("evt-001")
    assert q.full() is True


async def test_put_when_full_raises() -> None:
    q = AsyncioEventQueue(maxsize=1)
    await q.put("evt-001")
    with pytest.raises(asyncio.QueueFull):
        await q.put("evt-002")
