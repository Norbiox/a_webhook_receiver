"""
Requirements validation: 1000 unique new webhooks/minute from several external systems.

Requirement (docs/requirements.md):
    "~1000 webhooków/minutę z kilku systemów zewnętrznych"
    (~1000 webhooks/minute from several external systems)

Target:  ~17 new unique POST /webhooks per second sustained for 180s
Pass criteria:
    - error rate < 1%  (queue-full 429s are counted as errors here — they mean
                         the service is rejecting load it should accept)
    - p99 latency < 500ms

Run:
    uv run locust -f load_tests/locustfile_requirements.py --headless \\
        --run-time 90s --host http://localhost:8000

The shape ramps to 5 concurrent senders in 10s, holds for 180s, then stops.
Each sender uses constant_throughput(3.4) → 5 × 3.4 ≈ 17 req/s = 1020/min.
"""

import uuid

from locust import HttpUser, LoadTestShape, constant_throughput, task  # noqa: F401

# 5 simulated external systems, each sending ~3.4 webhooks/second
_SENDERS = 5
_RPS_PER_SENDER = 3.4  # 5 × 3.4 ≈ 17 req/s ≈ 1020/min


class ExternalSystem(HttpUser):
    """One external system sending a steady stream of unique webhooks."""

    wait_time = constant_throughput(_RPS_PER_SENDER)

    @task
    def post_new_webhook(self) -> None:
        payload = {
            "idempotency_key": str(uuid.uuid4()),
            "event_type": "order.created",
            "payload": {"amount": 99, "currency": "PLN"},
        }
        self.client.post("/webhooks", json=payload)


class RequirementsShape(LoadTestShape):
    """
    Ramp to target concurrency over 10s, hold for 180s, then stop.

    Timeline:
        0–10s   ramp from 0 → 5 users
        10–190s  hold at 5 users  ← measurement window
        190s+    stop (locust --run-time 210s handles the final teardown)
    """

    def tick(self) -> tuple[int, float] | None:
        t = self.get_run_time()
        if t < 10:
            return (_SENDERS, _SENDERS / 10)  # ramp: target users, spawn rate
        if t < 190:
            return (_SENDERS, _SENDERS)  # hold
        return None  # stop
