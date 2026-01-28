"""FastAPI application exposing the catalog pipeline as a service."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence

from fastapi import FastAPI, HTTPException, status

from .config import config
from .rate_limiter import TokenBucket
from .schemas import (
    APIError,
    EnrichBatchRequest,
    EnrichBatchResponse,
    EnrichedProductRecord,
    InferenceRequest,
    PredictBatchRequest,
    PredictBatchResponse,
    PredictedProductRecord,
    ProductRecord,
)
from .service_layer import (
    PipelineError,
    PredictInput,
    StageTimings,
    enrich_batch,
    enrich_one,
    predict_batch,
    predict_one,
    summarize_timings,
)

logger = logging.getLogger("catalog_intelligence_pipeline.api")

app = FastAPI(
    title="Catalog Intelligence Pipeline API",
    version="0.3.0",
    description="Reference FastAPI app with swappable vision/LLM providers.",
)


def _build_rate_limiter(limit: int) -> TokenBucket | None:
    if limit <= 0:
        return None
    return TokenBucket(limit)


_rate_limiter = _build_rate_limiter(config.rpm_limit)


@app.get("/health")
def health() -> dict[str, str]:
    """Lightweight health probe for orchestration/monitoring."""

    return {"status": "ok"}


@app.post("/v1/enrich", response_model=EnrichedProductRecord)
def enrich_v1(record: ProductRecord) -> EnrichedProductRecord:
    _enforce_rate_limit()
    _validate_text_lengths([record])
    try:
        enriched, timings = enrich_one(record)
    except PipelineError as exc:
        raise _http_error(exc) from exc

    _log_timings("POST /v1/enrich", [timings], total=1, errors=0)
    return enriched


@app.post("/v1/enrich/batch", response_model=EnrichBatchResponse)
def enrich_v1_batch(request: EnrichBatchRequest) -> EnrichBatchResponse:
    _enforce_rate_limit()
    _validate_batch_limit(len(request.items))
    _validate_text_lengths(request.items)
    items, errors, timings = enrich_batch(request.items)
    total = len(request.items)
    _log_timings("POST /v1/enrich/batch", timings, total=total, errors=len(errors))
    return EnrichBatchResponse(items=items, errors=errors)


@app.post("/v1/predict", response_model=PredictedProductRecord)
def predict_v1(record: PredictInput) -> PredictedProductRecord:
    _enforce_rate_limit()
    _validate_text_lengths([record])
    try:
        predicted, timings = predict_one(record)
    except PipelineError as exc:
        raise _http_error(exc) from exc

    _log_timings("POST /v1/predict", [timings], total=1, errors=0)
    return predicted


@app.post("/v1/predict/batch", response_model=PredictBatchResponse)
def predict_v1_batch(request: PredictBatchRequest) -> PredictBatchResponse:
    _enforce_rate_limit()
    _validate_batch_limit(len(request.items))
    _validate_text_lengths(request.items)
    items, errors, timings = predict_batch(request.items)
    total = len(request.items)
    _log_timings("POST /v1/predict/batch", timings, total=total, errors=len(errors))
    return PredictBatchResponse(items=items, errors=errors)


@app.post("/predict", response_model=PredictBatchResponse, deprecated=True)
def predict_legacy(request: InferenceRequest) -> PredictBatchResponse:
    """Deprecated endpoint retained for backwards compatibility."""

    batch_request = PredictBatchRequest(items=request.records)
    return predict_v1_batch(batch_request)


def _http_error(exc: PipelineError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=exc.error.model_dump(),
    )


def _log_timings(route: str, timings: Iterable[StageTimings], *, total: int, errors: int) -> None:
    summary = summarize_timings(timings)
    logger.info(
        (
            "route=%s total=%d errors=%d ingest_ms=%.2f enrich_ms=%.2f vision_ms=%.2f fuse_ms=%.2f total_ms=%.2f"
        ),
        route,
        total,
        errors,
        summary.ingest_ms,
        summary.enrich_ms,
        summary.vision_ms,
        summary.fuse_ms,
        summary.total_ms,
    )


def _validate_batch_limit(size: int) -> None:
    if size <= config.max_batch_items:
        return
    raise _request_limit_error(
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        APIError(
            product_id=None,
            error_type="batch_limit_exceeded",
            message=(
                f"Batch size {size} exceeds configured limit of {config.max_batch_items}."
            ),
            stage="request_validation",
        ),
    )


def _validate_text_lengths(records: Sequence[PredictInput]) -> None:
    limit = config.max_text_chars
    if limit <= 0:
        return

    for entry in records:
        title = getattr(entry, "title", "") or ""
        description = getattr(entry, "description", "") or ""
        total_chars = len(title) + len(description)
        if total_chars > limit:
            raise _request_limit_error(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                APIError(
                    product_id=getattr(entry, "product_id", None),
                    error_type="text_limit_exceeded",
                    message=(
                        f"title+description length {total_chars} exceeds limit of {limit} characters."
                    ),
                    stage="request_validation",
                ),
            )


def _enforce_rate_limit() -> None:
    limiter = _rate_limiter
    if limiter is None:
        return
    if limiter.consume():
        return
    raise _request_limit_error(
        status.HTTP_429_TOO_MANY_REQUESTS,
        APIError(
            product_id=None,
            error_type="rate_limited",
            message="Request rate exceeded per-minute limit.",
            stage="rate_limit",
        ),
    )


def _request_limit_error(status_code: int, error: APIError) -> HTTPException:
    return HTTPException(status_code=status_code, detail=error.model_dump())
