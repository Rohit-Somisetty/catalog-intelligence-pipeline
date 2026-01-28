"""JSON schema helpers for validating outbound Pub/Sub events."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema

_SCHEMA_FILENAME = "pubsub_catalog_predictions.schema.json"


def validate_event(event: dict[str, Any]) -> None:
    """Validate an event payload against the published JSON schema."""

    try:
        jsonschema.validate(instance=event, schema=_load_event_schema())
    except jsonschema.ValidationError as exc:  # pragma: no cover - exercised via tests
        raise ValueError(f"Event payload failed validation: {exc.message}") from exc


@lru_cache(maxsize=1)
def _load_event_schema() -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "contracts" / _SCHEMA_FILENAME
    if not schema_path.exists():  # pragma: no cover - defensive
        raise FileNotFoundError(f"Event schema not found at {schema_path}")
    return json.loads(schema_path.read_text(encoding="utf-8"))
