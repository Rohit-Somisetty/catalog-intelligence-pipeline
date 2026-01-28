from __future__ import annotations

from pathlib import Path

import duckdb

from catalog_intelligence_pipeline.config import AppConfig
from catalog_intelligence_pipeline.schemas import IngestedProductRecord
from catalog_intelligence_pipeline.service_layer import predict_one


def _build_record(sample_image_path: Path) -> IngestedProductRecord:
    return IngestedProductRecord(
        product_id="svc-001",
        title="Modern Sofa",
        description="A comfy sofa",
        image_url="https://example.com/sofa.jpg",
        image_path=str(sample_image_path),
        image_local_path=str(sample_image_path),
    )


def _build_config(
    tmp_path: Path,
    *,
    enable_publish: bool = False,
    validate_events: bool = False,
    enable_warehouse: bool = False,
) -> AppConfig:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    events_dir = tmp_path / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    warehouse_path = tmp_path / "warehouse.duckdb"
    warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    return AppConfig(
        cache_dir=cache_dir,
        ingest_timeout_s=5.0,
        fail_fast=False,
        events_dir=events_dir,
        publish_mode="local",
        enable_publish=enable_publish,
        validate_events=validate_events,
        warehouse_mode="duckdb",
        warehouse_path=warehouse_path,
        enable_warehouse=enable_warehouse,
        max_batch_items=25,
        max_text_chars=10000,
        rpm_limit=0,
        record_timeout_s=8.0,
    )


def test_predict_one_skips_publish_when_disabled(tmp_path: Path, sample_image_path: Path) -> None:
    cfg = _build_config(tmp_path)
    record = _build_record(sample_image_path)

    predict_one(record, cfg)

    topic_file = cfg.events_dir / "catalog_predictions.jsonl"
    assert not topic_file.exists()
    assert not cfg.warehouse_path.exists()


def test_predict_one_publishes_and_writes_warehouse(tmp_path: Path, sample_image_path: Path) -> None:
    cfg = _build_config(
        tmp_path,
        enable_publish=True,
        validate_events=True,
        enable_warehouse=True,
    )

    record = _build_record(sample_image_path)

    predict_one(record, cfg)

    topic_file = cfg.events_dir / "catalog_predictions.jsonl"
    assert topic_file.exists()
    content = topic_file.read_text(encoding="utf-8").strip()
    assert "svc-001" in content

    assert cfg.warehouse_path.exists()
    conn = duckdb.connect(str(cfg.warehouse_path))
    try:
        count = conn.execute("SELECT COUNT(*) FROM catalog__predictions").fetchone()[0]
    finally:
        conn.close()
    assert count >= 1
