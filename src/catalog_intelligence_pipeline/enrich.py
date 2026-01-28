"""Enrichment pipeline orchestrating text + dimension extractors."""

from __future__ import annotations

from .extractors import extract_dimensions_prediction, extract_text_attributes
from .schemas import AttributePrediction, EnrichedProductRecord, IngestedProductRecord

_ATTRIBUTE_KEYS = ["category", "room_type", "style", "material"]


def enrich_records(records: list[IngestedProductRecord]) -> list[EnrichedProductRecord]:
    """Return enriched product records with attribute predictions."""

    enriched: list[EnrichedProductRecord] = []
    for record in records:
        text_predictions = extract_text_attributes(record.title, record.description)
        dimension_prediction = extract_dimensions_prediction(record.title, record.description)
        predictions: dict[str, AttributePrediction] = {key: text_predictions[key] for key in _ATTRIBUTE_KEYS}
        predictions["dimensions"] = dimension_prediction

        enriched.append(
            EnrichedProductRecord(
                **record.model_dump(),
                predictions=predictions,
            )
        )
    return enriched
