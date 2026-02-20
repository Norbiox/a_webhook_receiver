FROM python:3.14-alpine

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN adduser -D appuser && mkdir -p /data && chown appuser:appuser /data

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/ ./src/

RUN uv sync --frozen --no-dev

USER appuser

VOLUME ["/data"]
EXPOSE 8000

ENV PATH="/app/.venv/bin:$PATH"

CMD ["uvicorn", "webhook_receiver.app:create_app", \
     "--factory", "--host", "0.0.0.0", "--port", "8000"]
