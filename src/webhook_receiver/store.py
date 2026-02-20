import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import aiosqlite


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class Event:
    id: str
    idempotency_key: str
    event_type: str
    payload: str
    status: str
    attempts: int
    last_error: str | None
    retry_after: str | None
    created_at: str
    updated_at: str


def _row_to_event(row: aiosqlite.Row) -> Event:
    return Event(*row)


class SQLiteIdempotencyStore:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def insert_or_get(self, request: dict) -> tuple[Event, bool]:
        now = _now()
        event_id = str(uuid.uuid4())
        payload = json.dumps(request["payload"])
        try:
            await self._conn.execute(
                "INSERT INTO events(id,idempotency_key,event_type,payload,status,"
                "attempts,last_error,retry_after,created_at,updated_at) "
                "VALUES(?,?,?,?,'pending',0,NULL,NULL,?,?)",
                (
                    event_id,
                    request["idempotency_key"],
                    request["event_type"],
                    payload,
                    now,
                    now,
                ),
            )
            await self._conn.commit()
        except aiosqlite.IntegrityError:
            return await self.get_by_idempotency_key(request["idempotency_key"]), False
        return await self.get_by_id(event_id), True

    async def get_by_id(self, event_id: str) -> Event | None:
        async with self._conn.execute("SELECT * FROM events WHERE id=?", (event_id,)) as cursor:
            row = await cursor.fetchone()
        return _row_to_event(row) if row else None

    async def get_by_idempotency_key(self, key: str) -> Event | None:
        async with self._conn.execute("SELECT * FROM events WHERE idempotency_key=?", (key,)) as cursor:
            row = await cursor.fetchone()
        return _row_to_event(row) if row else None

    async def mark_processing(self, event_id: str) -> None:
        await self._conn.execute(
            "UPDATE events SET status='processing', updated_at=? WHERE id=?",
            (_now(), event_id),
        )
        await self._conn.commit()

    async def mark_completed(self, event_id: str) -> None:
        await self._conn.execute(
            "UPDATE events SET status='completed', updated_at=? WHERE id=?",
            (_now(), event_id),
        )
        await self._conn.commit()

    async def mark_failed(
        self,
        event_id: str,
        error: str,
        max_attempts: int,
        base_delay: float,
        max_delay: float,
    ) -> None:
        event = await self.get_by_id(event_id)
        attempts = event.attempts + 1
        now = _now()
        if attempts < max_attempts:
            delay = min(base_delay * (2**attempts), max_delay)
            retry_after = (datetime.now(UTC) + timedelta(seconds=delay)).isoformat()
            await self._conn.execute(
                "UPDATE events SET status='pending', attempts=?, last_error=?, retry_after=?, updated_at=? WHERE id=?",
                (attempts, error, retry_after, now, event_id),
            )
        else:
            await self._conn.execute(
                "UPDATE events SET status='failed', attempts=?, last_error=?, updated_at=? WHERE id=?",
                (attempts, error, now, event_id),
            )
        await self._conn.commit()

    async def get_pending_ids(self, now: str) -> list[str]:
        async with self._conn.execute(
            "SELECT id FROM events WHERE status IN ('pending','processing')"
            " AND (retry_after IS NULL OR retry_after <= ?)"
            " ORDER BY created_at",
            (now,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def delete_expired(self, before: str) -> int:
        cursor = await self._conn.execute(
            "DELETE FROM events WHERE status IN ('completed','failed') AND created_at < ?",
            (before,),
        )
        await self._conn.commit()
        return cursor.rowcount
