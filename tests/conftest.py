import pytest
from httpx import ASGITransport, AsyncClient

from webhook_receiver.app import create_app
from webhook_receiver.config import Settings
from webhook_receiver.database import open_db
from webhook_receiver.dependencies import get_db, get_queue
from webhook_receiver.queue import AsyncioEventQueue


@pytest.fixture
async def db(tmp_path: pytest.TempPathFactory):
    conn = await open_db(str(tmp_path / "test.db"))
    yield conn
    await conn.close()


@pytest.fixture
async def client(tmp_path: pytest.TempPathFactory) -> AsyncClient:
    settings = Settings(db_path=str(tmp_path / "test.db"))
    app = create_app(settings)
    db = await open_db(settings.db_path)
    queue = AsyncioEventQueue(maxsize=settings.queue_maxsize)
    app.state.ready = True
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_queue] = lambda: queue
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    await db.close()
