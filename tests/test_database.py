import pytest

from webhook_receiver.database import open_db


async def test_events_table_created(tmp_path: pytest.TempPathFactory) -> None:
    conn = await open_db(str(tmp_path / "test.db"))
    async with conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'") as cursor:
        row = await cursor.fetchone()
    await conn.close()
    assert row is not None


async def test_wal_mode_enabled(tmp_path: pytest.TempPathFactory) -> None:
    conn = await open_db(str(tmp_path / "test.db"))
    async with conn.execute("PRAGMA journal_mode") as cursor:
        row = await cursor.fetchone()
    await conn.close()
    assert row[0] == "wal"


async def test_index_created(tmp_path: pytest.TempPathFactory) -> None:
    conn = await open_db(str(tmp_path / "test.db"))
    index_name = "idx_events_status_created_at"
    async with conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
        (index_name,),
    ) as cursor:
        row = await cursor.fetchone()
    await conn.close()
    assert row is not None
