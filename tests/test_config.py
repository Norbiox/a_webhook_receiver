import pytest

from webhook_receiver.config import Settings


def test_defaults() -> None:
    s = Settings()
    assert s.worker_count == 10
    assert s.queue_maxsize == 1000
    assert s.max_attempts == 5
    assert s.retry_base_delay == 5.0
    assert s.retry_max_delay == 300.0
    assert s.retention_days == 30
    assert s.cleanup_interval_hours == 1
    assert s.db_path == "/data/events.db"
    assert s.log_level == "INFO"
    assert s.log_format == "pretty"


def test_override_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKER_COUNT", "20")
    monkeypatch.setenv("DB_PATH", "/tmp/test.db")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    s = Settings()
    assert s.worker_count == 20
    assert s.db_path == "/tmp/test.db"
    assert s.log_level == "DEBUG"
