from httpx import AsyncClient


async def test_metrics_endpoint_returns_200(client: AsyncClient) -> None:
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


async def test_metrics_exposes_event_counter(client: AsyncClient) -> None:
    response = await client.get("/metrics")
    assert "webhook_events_total" in response.text


async def test_metrics_exposes_queue_depth(client: AsyncClient) -> None:
    response = await client.get("/metrics")
    assert "webhook_queue_depth" in response.text


async def test_metrics_exposes_processing_duration(client: AsyncClient) -> None:
    response = await client.get("/metrics")
    assert "webhook_processing_duration_seconds" in response.text


async def test_metrics_exposes_processing_errors(client: AsyncClient) -> None:
    response = await client.get("/metrics")
    assert "webhook_processing_errors_total" in response.text


async def test_post_webhook_increments_accepted_counter(client: AsyncClient) -> None:
    body = {"idempotency_key": "m-key-1", "event_type": "test", "payload": {}}
    await client.post("/webhooks", json=body)
    response = await client.get("/metrics")
    assert 'result="accepted"' in response.text


async def test_post_duplicate_increments_duplicate_counter(client: AsyncClient) -> None:
    body = {"idempotency_key": "m-key-2", "event_type": "test", "payload": {}}
    await client.post("/webhooks", json=body)
    await client.post("/webhooks", json=body)
    response = await client.get("/metrics")
    assert 'result="duplicate"' in response.text
