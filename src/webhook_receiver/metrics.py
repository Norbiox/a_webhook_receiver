from prometheus_client import Counter, Gauge, Histogram

EVENTS_TOTAL = Counter(
    "webhook_events_total",
    "Total webhook events received",
    ["result"],
)

QUEUE_DEPTH = Gauge(
    "webhook_queue_depth",
    "Current number of events in the processing queue",
)

PROCESSING_DURATION = Histogram(
    "webhook_processing_duration_seconds",
    "Event processing duration in seconds",
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

PROCESSING_ERRORS_TOTAL = Counter(
    "webhook_processing_errors_total",
    "Total number of processing errors",
)
