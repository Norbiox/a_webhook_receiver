from importlib.resources import files

import aiosqlite

_SCHEMA = files("webhook_receiver").joinpath("schema.sql").read_text()


async def open_db(db_path: str) -> aiosqlite.Connection:
    conn = await aiosqlite.connect(db_path)
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA busy_timeout=5000")
    await conn.executescript(_SCHEMA)
    return conn
