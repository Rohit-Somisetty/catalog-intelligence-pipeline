# syntax=docker/dockerfile:1.4

FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip \
 && pip install --no-cache-dir .

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CIP_CACHE_DIR=/app/.cache/images

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app/src ./src
COPY pyproject.toml README.md ./

EXPOSE 8000

CMD ["uvicorn", "catalog_intelligence_pipeline.api:app", "--host", "0.0.0.0", "--port", "8000"]
