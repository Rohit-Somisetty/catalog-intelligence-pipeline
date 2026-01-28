"""Runtime configuration and environment helpers for the catalog pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_CACHE_DIR = Path(".cache") / "images"
_DEFAULT_EVENTS_DIR = Path("outputs") / "events"
_DEFAULT_WAREHOUSE_DB = Path("outputs") / "warehouse.duckdb"
_DEFAULT_WAREHOUSE_DIR = Path("outputs") / "warehouse"
_DEFAULT_MAX_BATCH_ITEMS = 50
_DEFAULT_MAX_TEXT_CHARS = 10_000
_DEFAULT_RPM_LIMIT = 120
_DEFAULT_RECORD_TIMEOUT_S = 8.0


@dataclass(frozen=True)
class AppConfig:
    """Immutable application configuration."""

    cache_dir: Path
    ingest_timeout_s: float
    fail_fast: bool
    events_dir: Path
    publish_mode: str
    enable_publish: bool
    validate_events: bool
    warehouse_mode: str
    warehouse_path: Path
    enable_warehouse: bool
    max_batch_items: int
    max_text_chars: int
    rpm_limit: int
    record_timeout_s: float


def _parse_bool(value: str | None, fallback: bool) -> bool:
    if value is None:
        return fallback
    return value.lower() in {"1", "true", "yes", "on"}

def _parse_int(value: str | None, fallback: int, *, minimum: int = 1) -> int:
    if value is None:
        return fallback
    try:
        parsed = int(value)
    except ValueError:
        return fallback
    return fallback if parsed < minimum else parsed


def _parse_float(value: str | None, fallback: float, *, minimum: float | None = None) -> float:
    if value is None:
        return fallback
    try:
        parsed = float(value)
    except ValueError:
        return fallback
    if minimum is not None and parsed < minimum:
        return fallback
    return parsed


def load_config() -> AppConfig:
    """Load configuration from environment variables, applying defaults."""

    cache_dir = Path(os.getenv("CIP_CACHE_DIR", str(_DEFAULT_CACHE_DIR)))
    cache_dir.mkdir(parents=True, exist_ok=True)

    events_dir = Path(os.getenv("CIP_EVENTS_DIR", str(_DEFAULT_EVENTS_DIR)))
    events_dir.mkdir(parents=True, exist_ok=True)

    timeout = _parse_float(os.getenv("CIP_INGEST_TIMEOUT_S"), 10.0, minimum=0.1)

    fail_fast = _parse_bool(os.getenv("CIP_FAIL_FAST"), False)

    publish_mode = os.getenv("CIP_PUBLISH_MODE", "local").lower()
    enable_publish = _parse_bool(os.getenv("CIP_ENABLE_PUBLISH"), False)
    validate_events = _parse_bool(os.getenv("CIP_VALIDATE_EVENTS"), False)

    warehouse_mode = os.getenv("CIP_WAREHOUSE_MODE", "duckdb").lower()
    default_warehouse_path = (
        _DEFAULT_WAREHOUSE_DB if warehouse_mode == "duckdb" else _DEFAULT_WAREHOUSE_DIR
    )
    warehouse_path = Path(os.getenv("CIP_WAREHOUSE_PATH", str(default_warehouse_path)))
    if warehouse_mode == "csv":
        warehouse_path.mkdir(parents=True, exist_ok=True)
    else:
        warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    enable_warehouse = _parse_bool(os.getenv("CIP_ENABLE_WAREHOUSE"), False)

    max_batch_items = _parse_int(os.getenv("CIP_MAX_BATCH_ITEMS"), _DEFAULT_MAX_BATCH_ITEMS, minimum=1)
    max_text_chars = _parse_int(os.getenv("CIP_MAX_TEXT_CHARS"), _DEFAULT_MAX_TEXT_CHARS, minimum=1)
    rpm_limit = _parse_int(os.getenv("CIP_RPM_LIMIT"), _DEFAULT_RPM_LIMIT, minimum=0)
    record_timeout_s = _parse_float(
        os.getenv("CIP_RECORD_TIMEOUT_S"),
        _DEFAULT_RECORD_TIMEOUT_S,
        minimum=0.0,
    )

    return AppConfig(
        cache_dir=cache_dir,
        ingest_timeout_s=timeout,
        fail_fast=fail_fast,
        events_dir=events_dir,
        publish_mode=publish_mode,
        enable_publish=enable_publish,
        validate_events=validate_events,
        warehouse_mode=warehouse_mode,
        warehouse_path=warehouse_path,
        enable_warehouse=enable_warehouse,
        max_batch_items=max_batch_items,
        max_text_chars=max_text_chars,
        rpm_limit=rpm_limit,
        record_timeout_s=record_timeout_s,
    )


config = load_config()
"""Singleton config loaded at import time for convenience."""
