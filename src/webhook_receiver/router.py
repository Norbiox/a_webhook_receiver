import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from webhook_receiver.dependencies import get_queue, get_store
from webhook_receiver.metrics import EVENTS_TOTAL, QUEUE_DEPTH
from webhook_receiver.models import EventStatusResponse, WebhookRequest, WebhookResponse
from webhook_receiver.queue import AsyncioEventQueue
from webhook_receiver.store import SQLiteIdempotencyStore

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/webhooks")
async def post_webhook(
    body: WebhookRequest,
    store: SQLiteIdempotencyStore = Depends(get_store),
    queue: AsyncioEventQueue = Depends(get_queue),
) -> JSONResponse:
    event, is_new = await store.insert_or_get(body.model_dump())
    if is_new:
        if queue.full():
            logger.warning("Queue full, rejecting event %s", event.id)
            EVENTS_TOTAL.labels(result="rejected").inc()
            raise HTTPException(status_code=429, detail="Queue full, retry later")
        await queue.put(event.id)
        EVENTS_TOTAL.labels(result="accepted").inc()
        QUEUE_DEPTH.set(queue.qsize())
        logger.info("Accepted event %s type=%s", event.id, body.event_type)
    else:
        EVENTS_TOTAL.labels(result="duplicate").inc()
        logger.info("Duplicate event idempotency_key=%s", body.idempotency_key)
    response = WebhookResponse(
        id=event.id,
        idempotency_key=event.idempotency_key,
        status=event.status,
        created_at=event.created_at,
    )
    status_code = 202 if is_new else 200
    return JSONResponse(content=response.model_dump(), status_code=status_code)


@router.get("/webhooks/{event_id}")
async def get_by_id(
    event_id: str,
    store: SQLiteIdempotencyStore = Depends(get_store),
) -> EventStatusResponse:
    event = await store.get_by_id(event_id)
    if event is None:
        raise HTTPException(status_code=404)
    return EventStatusResponse(**event.__dict__)


@router.get("/webhooks")
async def get_by_idempotency_key(
    idempotency_key: str,
    store: SQLiteIdempotencyStore = Depends(get_store),
) -> EventStatusResponse:
    event = await store.get_by_idempotency_key(idempotency_key)
    if event is None:
        raise HTTPException(status_code=404)
    return EventStatusResponse(**event.__dict__)


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/ready")
async def ready(request: Request) -> dict:
    if not request.app.state.ready:
        raise HTTPException(status_code=503)
    return {"status": "ok"}
