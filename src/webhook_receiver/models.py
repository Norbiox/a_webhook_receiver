from typing import Any

from pydantic import BaseModel


class WebhookRequest(BaseModel):
    idempotency_key: str
    event_type: str
    payload: dict[str, Any]


class WebhookResponse(BaseModel):
    id: str
    idempotency_key: str
    status: str
    created_at: str


class EventStatusResponse(BaseModel):
    id: str
    idempotency_key: str
    status: str
    created_at: str
    updated_at: str
