from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    worker_count: int = 85
    queue_maxsize: int = 1000
    max_attempts: int = 5
    retry_base_delay: float = 5.0
    retry_max_delay: float = 300.0
    retention_days: int = 30
    cleanup_interval_hours: int = 1
    db_path: str = "/data/events.db"
    log_level: str = "INFO"
    log_format: str = "pretty"
