from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from catalog_intelligence_pipeline import api as api_module
from catalog_intelligence_pipeline import config as config_module
from catalog_intelligence_pipeline.api import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_api_config() -> Iterator[None]:
    original_cfg = api_module.config
    original_limiter = api_module._rate_limiter
    yield
    api_module.config = original_cfg
    config_module.config = original_cfg
    api_module._rate_limiter = original_limiter


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_enrich_endpoint(sample_image_path) -> None:
    payload = {
        "product_id": "enrich-001",
        "title": "Modern Sofa",
        "description": "A comfy modern sofa with performance fabric.",
        "image_path": str(sample_image_path),
    }

    response = client.post("/v1/enrich", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["product_id"] == "enrich-001"
    assert "predictions" in body
    assert "category" in body["predictions"]


def test_predict_endpoint(sample_image_path) -> None:
    payload = {
        "product_id": "predict-001",
        "title": "Walnut Coffee Table",
        "description": "Mid-century table with walnut veneer.",
        "image_path": str(sample_image_path),
    }

    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["product_id"] == "predict-001"
    assert "final_predictions" in body
    assert "decision_log" in body


def test_predict_batch_partial_failure(sample_image_path, tmp_path) -> None:
    valid = {
        "product_id": "predict-002",
        "title": "Dining Chair",
        "description": "Oak dining chair with cushion.",
        "image_path": str(sample_image_path),
    }
    missing_path = tmp_path / "missing.png"
    invalid = {
        "product_id": "predict-003",
        "title": "Accent Lamp",
        "description": "Metal desk lamp.",
        "image_path": str(missing_path),
    }

    response = client.post("/v1/predict/batch", json={"items": [valid, invalid]})
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert len(body["errors"]) == 1
    error = body["errors"][0]
    assert error["index"] == 1
    assert error["product_id"] == "predict-003"
    assert error["stage"] == "ingest"


def _override_api_config(**overrides):
    new_cfg = replace(api_module.config, **overrides)
    api_module.config = new_cfg
    config_module.config = new_cfg
    api_module._rate_limiter = api_module._build_rate_limiter(new_cfg.rpm_limit)


def _error_type(response):
    data = response.json()
    if "error_type" in data:
        return data["error_type"]
    return data.get("detail", {}).get("error_type")


def test_predict_batch_enforces_size_limit(sample_image_path) -> None:
    _override_api_config(max_batch_items=1)
    payload = {
        "items": [
            {
                "product_id": "limit-1",
                "title": "A",
                "description": "B",
                "image_path": str(sample_image_path),
            },
            {
                "product_id": "limit-2",
                "title": "C",
                "description": "D",
                "image_path": str(sample_image_path),
            },
        ]
    }

    response = client.post("/v1/predict/batch", json=payload)
    assert response.status_code == 413
    assert _error_type(response) == "batch_limit_exceeded"


def test_predict_text_limit(monkeypatch, sample_image_path) -> None:
    _override_api_config(max_text_chars=10)
    payload = {
        "product_id": "text-1",
        "title": "X" * 6,
        "description": "Y" * 10,
        "image_path": str(sample_image_path),
    }

    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 413
    assert _error_type(response) == "text_limit_exceeded"


def test_rate_limiter_returns_429(sample_image_path) -> None:
    _override_api_config(rpm_limit=1)
    payload = {
        "product_id": "rate-1",
        "title": "Chair",
        "description": "Oak chair",
        "image_path": str(sample_image_path),
    }

    first = client.post("/v1/predict", json=payload)
    assert first.status_code == 200

    second = client.post("/v1/predict", json=payload)
    assert second.status_code == 429
    assert _error_type(second) == "rate_limited"
