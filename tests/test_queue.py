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


async def test_put_beyond_maxsize_succeeds() -> None:
    # maxsize is a soft limit checked only by the router via full().
    # put() must never raise — startup load_pending must be able to enqueue
    # all pending events regardless of the configured queue capacity.
    q = AsyncioEventQueue(maxsize=1)
    await q.put("evt-001")
    assert q.full() is True
    await q.put("evt-002")  # must not raise
    assert q.qsize() == 2
