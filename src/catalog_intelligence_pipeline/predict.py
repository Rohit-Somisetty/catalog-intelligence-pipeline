"""Prediction pipeline that orchestrates enrichment, vision, and fusion."""

from __future__ import annotations

from collections.abc import Iterable
from time import perf_counter

from .enrich import enrich_records
from .extractors import map_vision_predictions
from .fusion import fuse_predictions
from .providers import MockVisionProvider, VisionProvider
from .schemas import EnrichedProductRecord, IngestedProductRecord, PredictedProductRecord


def ensure_enriched(
    records: Iterable[IngestedProductRecord | EnrichedProductRecord],
) -> list[EnrichedProductRecord]:
    enriched: list[EnrichedProductRecord] = []
    to_enrich: list[IngestedProductRecord] = []

    for record in records:
        if isinstance(record, EnrichedProductRecord):
            enriched.append(record)
        else:
            to_enrich.append(record)

    if to_enrich:
        enriched.extend(enrich_records(to_enrich))

    return enriched


def predict_records(
    records: Iterable[EnrichedProductRecord],
    vision_provider: VisionProvider | None = None,
) -> list[PredictedProductRecord]:
    provider = vision_provider or MockVisionProvider()
    outputs: list[PredictedProductRecord] = []

    for record in records:
        predicted, _, _ = predict_record_with_diagnostics(record, provider)
        outputs.append(predicted)

    return outputs


def predict_record_with_diagnostics(
    record: EnrichedProductRecord,
    vision_provider: VisionProvider | None = None,
) -> tuple[PredictedProductRecord, float, float]:
    """Predict a single record while returning vision/fusion timings (ms)."""

    provider = vision_provider or MockVisionProvider()
    vision_start = perf_counter()
    vision_prediction = provider.predict(record.image_local_path)
    vision_ms = (perf_counter() - vision_start) * 1000

    fuse_start = perf_counter()
    vision_attributes = map_vision_predictions(vision_prediction)
    fused, decision_log = fuse_predictions(
        text_predictions=record.predictions,
        vision_predictions=vision_attributes,
        quality_flags=vision_prediction.quality_flags,
    )
    fuse_ms = (perf_counter() - fuse_start) * 1000

    predicted = PredictedProductRecord(
        **record.model_dump(),
        final_predictions=fused,
        decision_log=decision_log,
    )

    return predicted, vision_ms, fuse_ms