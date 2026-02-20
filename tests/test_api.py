import pytest
from httpx import ASGITransport, AsyncClient

from webhook_receiver.app import create_app
from webhook_receiver.config import Settings
from webhook_receiver.database import open_db
from webhook_receiver.dependencies import get_db, get_queue
from webhook_receiver.queue import AsyncioEventQueue

WEBHOOK = {
    "idempotency_key": "evt-001",
    "event_type": "order.created",
    "payload": {"order_id": "ORD-1234"},
}


async def test_post_webhook_returns_202(client: AsyncClient) -> None:
    response = await client.post("/webhooks", json=WEBHOOK)
    assert response.status_code == 202


async def test_post_webhook_response_shape(client: AsyncClient) -> None:
    response = await client.post("/webhooks", json=WEBHOOK)
    body = response.json()
    assert "id" in body
    assert body["idempotency_key"] == "evt-001"
    assert body["status"] == "pending"
    assert "created_at" in body


async def test_post_duplicate_returns_200(client: AsyncClient) -> None:
    await client.post("/webhooks", json=WEBHOOK)
    response = await client.post("/webhooks", json=WEBHOOK)
    assert response.status_code == 200


async def test_post_duplicate_same_shape(client: AsyncClient) -> None:
    first = await client.post("/webhooks", json=WEBHOOK)
    second = await client.post("/webhooks", json=WEBHOOK)
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["idempotency_key"] == second.json()["idempotency_key"]


async def test_get_by_id(client: AsyncClient) -> None:
    created = (await client.post("/webhooks", json=WEBHOOK)).json()
    response = await client.get(f"/webhooks/{created['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert "updated_at" in body


async def test_get_by_id_not_found(client: AsyncClient) -> None:
    response = await client.get("/webhooks/nonexistent-id")
    assert response.status_code == 404


async def test_get_by_idempotency_key(client: AsyncClient) -> None:
    created = (await client.post("/webhooks", json=WEBHOOK)).json()
    response = await client.get("/webhooks", params={"idempotency_key": "evt-001"})
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


async def test_get_by_idempotency_key_not_found(client: AsyncClient) -> None:
    response = await client.get("/webhooks", params={"idempotency_key": "missing"})
    assert response.status_code == 404


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200


async def test_ready(client: AsyncClient) -> None:
    response = await client.get("/ready")
    assert response.status_code == 200


@pytest.fixture
async def full_queue_client(tmp_path: pytest.TempPathFactory) -> AsyncClient:
    settings = Settings(db_path=str(tmp_path / "test.db"))
    app = create_app(settings)
    db = await open_db(settings.db_path)
    queue = AsyncioEventQueue(maxsize=1)
    await queue.put("blocker")
    app.state.ready = True
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_queue] = lambda: queue
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    await db.close()


async def test_post_returns_429_when_queue_full(
    full_queue_client: AsyncClient,
) -> None:
    response = await full_queue_client.post("/webhooks", json=WEBHOOK)
    assert response.status_code == 429


async def test_ready_returns_503_when_not_ready(
    tmp_path: pytest.TempPathFactory,
) -> None:
    settings = Settings(db_path=str(tmp_path / "test.db"))
    app = create_app(settings)
    db = await open_db(settings.db_path)
    app.state.ready = False
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_queue] = lambda: AsyncioEventQueue(maxsize=10)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.get("/ready")
    await db.close()
    assert response.status_code == 503
