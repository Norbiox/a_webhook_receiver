"""
Locust load tests for the webhook receiver API.

Run against a local server:
    uv run uvicorn webhook_receiver.app:create_app --factory --host 0.0.0.0 --port 8000

Headless benchmark (60 s, 50 users, ramp 10/s):
    uv run locust -f load_tests/locustfile.py --headless \
        -u 50 -r 10 --run-time 60s --host http://localhost:8000

Interactive web UI:
    uv run locust -f load_tests/locustfile.py --host http://localhost:8000
"""

import uuid

from locust import HttpUser, between, task


class WebhookIngestionUser(HttpUser):
    """Simulates a producer submitting new unique webhook events."""

    wait_time = between(0.05, 0.2)
    weight = 3

    @task
    def post_new_webhook(self) -> None:
        payload = {
            "idempotency_key": str(uuid.uuid4()),
            "event_type": "order.created",
            "payload": {"amount": 99, "currency": "USD"},
        }
        with self.client.post("/webhooks", json=payload, catch_response=True) as resp:
            if resp.status_code == 429:
                resp.success()  # expected under heavy load — queue full


class DuplicateIngestionUser(HttpUser):
    """Simulates a producer retrying the same event (idempotency path)."""

    wait_time = between(0.1, 0.5)
    weight = 1

    def on_start(self) -> None:
        self._key = str(uuid.uuid4())
        self.client.post(
            "/webhooks",
            json={"idempotency_key": self._key, "event_type": "order.created", "payload": {}},
        )

    @task
    def post_duplicate_webhook(self) -> None:
        self.client.post(
            "/webhooks",
            json={"idempotency_key": self._key, "event_type": "order.created", "payload": {}},
        )


class StatusCheckUser(HttpUser):
    """Simulates a consumer polling event status by idempotency key."""

    wait_time = between(0.1, 0.5)
    weight = 2

    def on_start(self) -> None:
        self._key = str(uuid.uuid4())
        resp = self.client.post(
            "/webhooks",
            json={"idempotency_key": self._key, "event_type": "order.created", "payload": {}},
        )
        self._event_id = resp.json().get("id") if resp.status_code in (200, 202) else None

    @task(3)
    def get_status_by_id(self) -> None:
        if self._event_id:
            self.client.get(f"/webhooks/{self._event_id}")

    @task(1)
    def get_status_by_idempotency_key(self) -> None:
        self.client.get("/webhooks", params={"idempotency_key": self._key})

    @task(1)
    def get_health(self) -> None:
        self.client.get("/health")
