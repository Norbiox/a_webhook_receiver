import asyncio
from typing import Protocol


class EventQueue(Protocol):
    async def put(self, event_id: str) -> None: ...

    async def get(self) -> str: ...

    def full(self) -> bool: ...

    def qsize(self) -> int: ...


class AsyncioEventQueue:
    def __init__(self, maxsize: int) -> None:
        self._q: asyncio.Queue[str] = asyncio.Queue(maxsize=maxsize)

    async def put(self, event_id: str) -> None:
        self._q.put_nowait(event_id)

    async def get(self) -> str:
        return await self._q.get()

    def full(self) -> bool:
        return self._q.full()

    def qsize(self) -> int:
        return self._q.qsize()
