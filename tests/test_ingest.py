from __future__ import annotations

import json
from pathlib import Path

import pytest

from catalog_intelligence_pipeline import ingest
from catalog_intelligence_pipeline.schemas import RawProductRecord


def test_load_records_from_json(tmp_path: Path) -> None:
    payload = [
        {
            "product_id": "json-001",
            "title": "Minimal Chair",
            "description": "Compact dining chair.",
            "image_url": "https://example.com/chair.jpg",
        }
    ]
    path = tmp_path / "records.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    records = ingest.load_records(path)

    assert len(records) == 1
    assert records[0].product_id == "json-001"


def test_load_records_from_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "product_id": "jsonl-001",
                        "title": "Floor Lamp",
                        "description": None,
                        "image_url": "https://example.com/lamp.png",
                    }
                )
            ]
        ),
        encoding="utf-8",
    )

    records = ingest.load_records(path)

    assert len(records) == 1
    assert records[0].product_id == "jsonl-001"


def test_raw_product_record_requires_image_source() -> None:
    with pytest.raises(ValueError):
        RawProductRecord(
            product_id="no-image",
            title="Mystery Object",
            description=None,
        )


def test_resolve_images_reuses_cached_download(monkeypatch, tmp_path: Path, sample_image_bytes: bytes) -> None:
    record = RawProductRecord(
        product_id="cache-test",
        title="Side Table",
        description="",
        image_url="https://example.com/table.png",
    )
    cache_dir = tmp_path / ".cache"
    calls: list[str] = []

    class DummyResponse:
        def __init__(self, content: bytes) -> None:
            self.content = content

        def raise_for_status(self) -> None:  # pragma: no cover - trivial
            return None

    def fake_get(url: str, timeout: float) -> DummyResponse:
        calls.append(url)
        return DummyResponse(sample_image_bytes)

    monkeypatch.setattr(ingest.requests, "get", fake_get)

    first_run, errors = ingest.resolve_images([record], cache_dir=cache_dir, timeout_s=5.0)
    assert len(first_run) == 1
    assert not errors
    assert len(calls) == 1

    second_run, _ = ingest.resolve_images([record], cache_dir=cache_dir, timeout_s=5.0)
    assert len(second_run) == 1
    assert len(calls) == 1, "Expected cached file to skip re-download"


def test_resolve_images_validates_local_path(sample_image_path: Path, tmp_path: Path) -> None:
    record = RawProductRecord(
        product_id="local-001",
        title="Desk",
        description=None,
        image_path=str(sample_image_path),
    )

    ingested, errors = ingest.resolve_images([record], cache_dir=tmp_path)

    assert len(ingested) == 1
    assert not errors
    assert ingested[0].image_local_path == str(sample_image_path)


def test_resolve_images_reports_missing_local_file(tmp_path: Path) -> None:
    record = RawProductRecord(
        product_id="missing-001",
        title="Bench",
        description=None,
        image_path=str(tmp_path / "missing.jpg"),
    )

    ingested, errors = ingest.resolve_images([record], cache_dir=tmp_path)

    assert not ingested
    assert len(errors) == 1
    assert errors[0].error_type == "missing_local_file"
