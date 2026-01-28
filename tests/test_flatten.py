from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from pydantic import HttpUrl

from catalog_intelligence_pipeline.flatten import flatten_predicted_record_to_row
from catalog_intelligence_pipeline.schemas import (
    AttributePrediction,
    DecisionLogEntry,
    PredictedProductRecord,
)


def _attr(value: str, confidence: float) -> AttributePrediction:
    return AttributePrediction(value=value, confidence=confidence, extracted_by="test", evidence=[])


def test_flatten_predicted_record_to_row() -> None:
    predictions = {
        "category": _attr("Table", 0.9),
        "room_type": _attr("Dining Room", 0.92),
        "style": _attr("Mid-Century", 0.85),
        "material": _attr("Walnut", 0.8),
    }

    record = PredictedProductRecord(
        product_id="prod-1",
        title="Walnut Table",
        description="",
        image_url=cast(HttpUrl, "https://example.com/image.jpg"),
        image_path="/tmp/image.jpg",
        image_local_path="/tmp/image.jpg",
        predictions={**predictions, "dimensions": _attr("", 0.0)},
        final_predictions=predictions,
        decision_log={
            "category": DecisionLogEntry(
                sources_considered=["text", "vision"],
                chosen_source="text",
                reason="Text higher confidence",
                conflicts=[],
            )
        },
    )

    event_ts = datetime.now(UTC)
    row = flatten_predicted_record_to_row(record, "event-123", event_ts)

    assert row["event_id"] == "event-123"
    assert row["event_ts"] == event_ts
    assert row["category_value"] == "Table"
    assert row["category_confidence"] == 0.9
    assert "raw_payload" in row
