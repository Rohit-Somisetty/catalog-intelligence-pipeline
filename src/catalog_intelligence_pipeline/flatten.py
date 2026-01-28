"""Helpers that flatten prediction records into warehouse-friendly rows."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .schemas import AttributePrediction, PredictedProductRecord

_ATTR_KEYS = ["category", "room_type", "style", "material"]


def flatten_predicted_record_to_row(
    record: PredictedProductRecord,
    event_id: str,
    event_ts: datetime,
) -> dict[str, Any]:
    """Convert a prediction into the flattened schema expected by the warehouse sinks."""

    row: dict[str, Any] = {
        "event_id": event_id,
        "event_ts": event_ts,
        "product_id": record.product_id,
    }

    for key in _ATTR_KEYS:
        attr = record.final_predictions.get(key)
        row[f"{key}_value"] = _attr_value(attr)
        row[f"{key}_confidence"] = _attr_confidence(attr)

    row["raw_payload"] = json.dumps(record.model_dump(mode="json"))
    return row


def _attr_value(attr: AttributePrediction | None) -> Any:
    return attr.value if attr else None


def _attr_confidence(attr: AttributePrediction | None) -> float | None:
    return attr.confidence if attr else None
