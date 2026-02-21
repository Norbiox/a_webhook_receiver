"""
Final requirements validation: 1000 unique new webhooks/minute under realistic
mixed traffic (ingestion + duplicates + status polling).

Requirement (docs/requirements.md):
    "~1000 webhooków/minutę z kilku systemów zewnętrznych"

User mix (20 total):
    ExternalSystem        5 (fixed)  — new unique POSTs, constant_throughput(3.4)
                                       5 × 3.4 ≈ 17 req/s ≈ 1020/min
    DuplicateIngestionUser  5        — retries of existing keys (idempotency path)
    StatusCheckUser        10        — GET by id / idempotency_key / health

Pass criteria:
    - POST /webhooks error rate < 1%  (429 counts as failure — the service must
                                       keep up with 1000/min, not shed the load)
    - p99 latency < 500ms

Run:
    uv run locust -f load_tests/locustfile_final.py --headless \\
        --run-time 90s --host http://localhost:8000

Interactive:
    uv run locust -f load_tests/locustfile_final.py --host http://localhost:8000
"""

import uuid

from locust import HttpUser, LoadTestShape, between, constant_throughput, task

_INGESTION_USERS = 5
_RPS_PER_SENDER = 3.4  # 5 × 3.4 ≈ 17 req/s ≈ 1020 new webhooks/min
_TOTAL_USERS = 20
_RAMP_SECONDS = 10
_HOLD_SECONDS = 180


class ExternalSystem(HttpUser):
    """5 external systems each sending a steady stream of new unique webhooks."""

    fixed_count = _INGESTION_USERS
    wait_time = constant_throughput(_RPS_PER_SENDER)

    @task
    def post_new_webhook(self) -> None:
        payload = {
            "idempotency_key": str(uuid.uuid4()),
            "event_type": "order.created",
            "payload": {"amount": 99, "currency": "PLN"},
        }
        self.client.post("/webhooks", json=payload)


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
    """Simulates a consumer polling event status."""

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


class FinalShape(LoadTestShape):
    def tick(self) -> tuple[int, float] | None:
        t = self.get_run_time()
        if t < _RAMP_SECONDS:
            return (_TOTAL_USERS, _TOTAL_USERS / _RAMP_SECONDS)
        if t < _RAMP_SECONDS + _HOLD_SECONDS:
            return (_TOTAL_USERS, _TOTAL_USERS)
        return None
