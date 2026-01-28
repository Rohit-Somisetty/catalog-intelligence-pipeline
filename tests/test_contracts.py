from __future__ import annotations

import pytest

from catalog_intelligence_pipeline.contracts import validate_event


@pytest.fixture()
def valid_event_payload() -> dict:
    return {
        "event_id": "event-123",
        "event_ts": "2025-01-01T00:00:00Z",
        "source": "catalog-intel.api",
        "version": "v1",
        "product_id": "prod-1",
        "predictions": {
            "category": {"value": "Table", "confidence": 0.9, "extracted_by": "fusion"},
            "room_type": {"value": "Dining Room", "confidence": 0.92, "extracted_by": "fusion"},
            "style": {"value": "Mid-Century", "confidence": 0.8, "extracted_by": "llm_stub"},
            "material": {"value": "Walnut", "confidence": 0.78, "extracted_by": "llm_stub"},
        },
    }


def test_validate_event_accepts_valid_payload(valid_event_payload: dict) -> None:
    validate_event(valid_event_payload)


def test_validate_event_rejects_invalid_payload(valid_event_payload: dict) -> None:
    invalid = valid_event_payload.copy()
    invalid.pop("product_id")
    with pytest.raises(ValueError):
        validate_event(invalid)
