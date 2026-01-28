"""Service-layer helpers that orchestrate pipeline stages for the API."""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter

from pydantic import ValidationError

from .config import AppConfig
from .config import config as default_config
from .contracts import validate_event
from .enrich import enrich_records
from .flatten import flatten_predicted_record_to_row
from .gcp_seams.publishers import LocalFilePublisher, Publisher, StubPubSubPublisher
from .gcp_seams.warehouse import LocalCSVSink, LocalDuckDBSink, StubBigQuerySink, WarehouseSink
from .ingest import resolve_images
from .predict import predict_record_with_diagnostics
from .schemas import (
    APIError,
    AttributePrediction,
    EnrichedProductRecord,
    IndexedAPIError,
    IngestedProductRecord,
    PredictedProductRecord,
    ProductRecord,
    RawProductRecord,
)

PredictInput = ProductRecord | EnrichedProductRecord


@dataclass
class StageTimings:
    """Tracks elapsed time (ms) spent in each pipeline stage."""

    ingest_ms: float = 0.0
    enrich_ms: float = 0.0
    vision_ms: float = 0.0
    fuse_ms: float = 0.0

    @property
    def predict_ms(self) -> float:
        return self.vision_ms + self.fuse_ms

    @property
    def total_ms(self) -> float:
        return self.ingest_ms + self.enrich_ms + self.predict_ms


class PipelineError(Exception):
    """Error raised when a pipeline stage fails for a single record."""

    def __init__(self, error: APIError) -> None:
        super().__init__(error.message)
        self.error = error


def _check_timeout(stage: str, product_id: str | None, started_at: float, cfg: AppConfig) -> None:
    if cfg.record_timeout_s <= 0:
        return

    elapsed = perf_counter() - started_at
    if elapsed <= cfg.record_timeout_s:
        return

    raise PipelineError(
        APIError(
            product_id=product_id,
            error_type="timeout",
            message=f"Record exceeded {cfg.record_timeout_s:.2f}s limit during {stage} stage.",
            stage=stage,
            details={"elapsed_s": elapsed, "limit_s": cfg.record_timeout_s},
        )
    )


def summarize_timings(timings: Iterable[StageTimings]) -> StageTimings:
    summary = StageTimings()
    for item in timings:
        summary.ingest_ms += item.ingest_ms
        summary.enrich_ms += item.enrich_ms
        summary.vision_ms += item.vision_ms
        summary.fuse_ms += item.fuse_ms
    return summary


def enrich_one(
    record: ProductRecord,
    cfg: AppConfig = default_config,
    *,
    started_at: float | None = None,
) -> tuple[EnrichedProductRecord, StageTimings]:
    record_start = started_at or perf_counter()
    timings = StageTimings()
    ingested = _ensure_ingested(record, cfg, timings)
    _check_timeout("ingest", record.product_id, record_start, cfg)

    enrich_start = perf_counter()
    try:
        enriched = enrich_records([ingested])[0]
    except Exception as exc:  # pragma: no cover - defensive guard
        raise PipelineError(
            APIError(
                product_id=record.product_id,
                error_type="enrich_failure",
                message=str(exc),
                stage="enrich",
            )
        ) from exc
    finally:
        timings.enrich_ms += (perf_counter() - enrich_start) * 1000

    _check_timeout("enrich", record.product_id, record_start, cfg)

    return enriched, timings


def enrich_batch(
    records: Sequence[ProductRecord],
    cfg: AppConfig = default_config,
) -> tuple[list[EnrichedProductRecord], list[IndexedAPIError], list[StageTimings]]:
    items: list[EnrichedProductRecord] = []
    errors: list[IndexedAPIError] = []
    timings: list[StageTimings] = []

    for index, record in enumerate(records):
        try:
            enriched, timing = enrich_one(record, cfg)
        except PipelineError as exc:
            errors.append(_indexed_error(exc.error, index))
            continue
        items.append(enriched)
        timings.append(timing)

    return items, errors, timings


def predict_one(
    record: PredictInput,
    cfg: AppConfig = default_config,
    *,
    process_outputs: bool = True,
) -> tuple[PredictedProductRecord, StageTimings]:
    record_start = perf_counter()
    if isinstance(record, EnrichedProductRecord):
        enriched_record = record
        timings = StageTimings()
    else:
        enriched_record, timings = enrich_one(record, cfg, started_at=record_start)

    predict_start = perf_counter()
    vision_ms = 0.0
    fuse_ms = 0.0
    try:
        predicted, vision_ms, fuse_ms = predict_record_with_diagnostics(enriched_record)
    except Exception as exc:  # pragma: no cover - defensive guard
        raise PipelineError(
            APIError(
                product_id=enriched_record.product_id,
                error_type="predict_failure",
                message=str(exc),
                stage="predict",
            )
        ) from exc
    finally:
        elapsed = (perf_counter() - predict_start) * 1000
        timings.vision_ms += vision_ms
        timings.fuse_ms += fuse_ms
        if timings.vision_ms + timings.fuse_ms == 0:
            # Fallback when diagnostics aren't captured.
            timings.vision_ms += elapsed

    _check_timeout("predict", enriched_record.product_id, record_start, cfg)

    if process_outputs:
        _process_outputs([predicted], cfg)
    return predicted, timings


def predict_batch(
    records: Sequence[PredictInput],
    cfg: AppConfig = default_config,
) -> tuple[list[PredictedProductRecord], list[IndexedAPIError], list[StageTimings]]:
    items: list[PredictedProductRecord] = []
    errors: list[IndexedAPIError] = []
    timings: list[StageTimings] = []

    for index, record in enumerate(records):
        try:
            predicted, timing = predict_one(record, cfg, process_outputs=False)
        except PipelineError as exc:
            errors.append(_indexed_error(exc.error, index))
            continue
        items.append(predicted)
        timings.append(timing)

    _process_outputs(items, cfg)
    return items, errors, timings


def _indexed_error(error: APIError, index: int) -> IndexedAPIError:
    payload = error.model_dump()
    payload["index"] = index
    return IndexedAPIError(**payload)


def _ensure_ingested(record: ProductRecord, cfg: AppConfig, timings: StageTimings) -> IngestedProductRecord:
    ingest_start = perf_counter()

    try:
        if isinstance(record, IngestedProductRecord):
            ingested = record
        elif record.image_local_path:
            ingested = IngestedProductRecord.model_validate(record.model_dump())
        else:
            raw = RawProductRecord.model_validate(record.model_dump())
            ingested, ingest_error = _ingest_raw(raw, cfg)
            if ingest_error:
                raise PipelineError(ingest_error)
            if ingested is None:  # pragma: no cover - defensive guard
                raise PipelineError(
                    APIError(
                        product_id=record.product_id,
                        error_type="ingest_failure",
                        message="Unknown ingestion failure.",
                        stage="ingest",
                    )
                )
    except ValidationError as exc:
        raise PipelineError(
            APIError(
                product_id=record.product_id,
                error_type="validation_error",
                message="Record failed validation during ingestion.",
                stage="ingest",
                details={"errors": exc.errors()},
            )
        ) from exc
    finally:
        timings.ingest_ms += (perf_counter() - ingest_start) * 1000

    return ingested


def _ingest_raw(raw: RawProductRecord, cfg: AppConfig) -> tuple[IngestedProductRecord | None, APIError | None]:
    try:
        ingested, errors = resolve_images(
            [raw],
            cache_dir=cfg.cache_dir,
            timeout_s=cfg.ingest_timeout_s,
            fail_fast=cfg.fail_fast,
        )
    except Exception as exc:  # pragma: no cover - network/IO guard
        return None, APIError(
            product_id=raw.product_id,
            error_type="ingest_failure",
            message=str(exc),
            stage="ingest",
        )

    if errors:
        detail = errors[0]
        return None, APIError(
            product_id=detail.product_id,
            error_type=detail.error_type,
            message=detail.message,
            stage="ingest",
        )

    return ingested[0], None


def _process_outputs(records: Sequence[PredictedProductRecord], cfg: AppConfig) -> None:
    if not records:
        return

    publisher = _build_publisher(cfg) if cfg.enable_publish else None
    sink = _build_sink(cfg) if cfg.enable_warehouse else None

    rows: list[dict] = []

    for record in records:
        event_id = uuid.uuid4().hex
        event_ts = datetime.now(UTC)

        if publisher:
            payload = _build_event_payload(record, event_id, event_ts)
            if cfg.validate_events:
                try:
                    validate_event(payload)
                except ValueError as exc:
                    raise PipelineError(
                        APIError(
                            product_id=record.product_id,
                            error_type="event_validation_error",
                            message=str(exc),
                            stage="publish",
                        )
                    ) from exc
            try:
                publisher.publish("catalog_predictions", payload)
            except Exception as exc:  # pragma: no cover - defensive
                raise PipelineError(
                    APIError(
                        product_id=record.product_id,
                        error_type="publish_failure",
                        message=str(exc),
                        stage="publish",
                    )
                ) from exc

        if sink:
            rows.append(flatten_predicted_record_to_row(record, event_id, event_ts))

    if sink and rows:
        try:
            sink.write_table("catalog", "predictions", rows)
        except Exception as exc:  # pragma: no cover - defensive
            raise PipelineError(
                APIError(
                    product_id=rows[0]["product_id"],
                    error_type="warehouse_failure",
                    message=str(exc),
                    stage="warehouse",
                )
            ) from exc


def _build_publisher(cfg: AppConfig) -> Publisher:
    if cfg.publish_mode == "local":
        return LocalFilePublisher(cfg.events_dir)
    return StubPubSubPublisher()


def _build_sink(cfg: AppConfig) -> WarehouseSink:
    if cfg.warehouse_mode == "duckdb":
        return LocalDuckDBSink(cfg.warehouse_path)
    if cfg.warehouse_mode == "csv":
        return LocalCSVSink(cfg.warehouse_path)
    return StubBigQuerySink()


def _build_event_payload(
    record: PredictedProductRecord,
    event_id: str,
    event_ts: datetime,
) -> dict:
    payload = {
        "event_id": event_id,
        "event_ts": event_ts.isoformat(),
        "source": "catalog-intel.api",
        "version": "v1",
        "product_id": record.product_id,
        "predictions": _serialize_predictions(record.final_predictions),
    }
    if record.decision_log:
        payload["decision_log"] = {key: value.model_dump() for key, value in record.decision_log.items()}
    return payload


def _serialize_predictions(predictions: dict[str, AttributePrediction]) -> dict[str, dict]:
    serialized: dict[str, dict] = {}
    for key, value in predictions.items():
        serialized[key] = {
            "value": value.value,
            "confidence": value.confidence,
            "extracted_by": value.extracted_by,
        }
    return serialized
