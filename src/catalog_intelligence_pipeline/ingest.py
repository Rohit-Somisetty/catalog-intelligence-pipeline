"""Data ingestion utilities for the catalog intelligence pipeline."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import requests
from PIL import Image, UnidentifiedImageError
from requests.exceptions import RequestException

from .schemas import IngestedProductRecord, IngestError, RawProductRecord

_SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
_JSON_SUFFIXES = {".json", ".jsonl"}


@runtime_checkable
class SupportsModelDump(Protocol):
    """Subset of Pydantic models that expose model_dump()."""

    def model_dump(self, *args: Any, **kwargs: Any) -> Any: ...


class IngestException(Exception):
    """Exception raised for recoverable ingest failures."""

    def __init__(self, error_type: str, message: str) -> None:
        super().__init__(message)
        self.error_type = error_type


def read_json_payload(path: Path | str) -> list[dict[str, Any]]:
    """Load structured data from either JSON or JSONL inputs."""

    source = Path(path)
    suffix = source.suffix.lower()
    if suffix not in _JSON_SUFFIXES:
        raise ValueError(f"Unsupported file format for {source}. Use .json or .jsonl inputs.")

    if suffix == ".json":
        payload = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("JSON file must contain a list of records.")
        return payload

    items: list[dict[str, Any]] = []
    with source.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            record = json.loads(stripped)
            if not isinstance(record, dict):
                raise ValueError("Each JSONL line must decode to an object.")
            items.append(record)
    return items


def load_records(path: Path | str) -> list[RawProductRecord]:
    """Parse raw catalog payloads from disk into validated models."""

    rows = read_json_payload(path)
    return [RawProductRecord.model_validate(row) for row in rows]


def resolve_images(
    records: Sequence[RawProductRecord],
    cache_dir: Path | str,
    timeout_s: float = 10.0,
    fail_fast: bool = False,
) -> tuple[list[IngestedProductRecord], list[IngestError]]:
    """Download or validate images, returning ingested records and structured errors."""

    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    ingested: list[IngestedProductRecord] = []
    errors: list[IngestError] = []

    for record in records:
        try:
            image_local_path = _resolve_image_location(record, cache_path, timeout_s)
            payload = record.model_dump()
            payload["image_local_path"] = str(image_local_path)
            ingested.append(IngestedProductRecord.model_validate(payload))
        except IngestException as exc:
            error = IngestError(
                product_id=record.product_id,
                error_type=exc.error_type,
                message=str(exc),
            )
            errors.append(error)
            if fail_fast:
                raise RuntimeError(f"Ingest failed for {record.product_id}: {exc}") from exc

    return ingested, errors


def write_jsonl(path: Path | str, items: Iterable[Any]) -> None:
    """Persist an iterable of items to JSONL format."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("w", encoding="utf-8") as handle:
        for item in items:
            if isinstance(item, SupportsModelDump):
                payload = item.model_dump(mode="json")
            else:
                payload = item
            handle.write(json.dumps(payload))
            handle.write("\n")


def _resolve_image_location(record: RawProductRecord, cache_dir: Path, timeout_s: float) -> Path:
    if record.image_path:
        return _validate_existing_image(Path(record.image_path))
    if record.image_url:
        return _download_image(record.product_id, str(record.image_url), cache_dir, timeout_s)
    raise IngestException("missing_image_source", "Record is missing both image_url and image_path.")


def _validate_existing_image(path: Path) -> Path:
    if not path.exists():
        raise IngestException("missing_local_file", f"Local image not found: {path}")

    ext = path.suffix.lower()
    if ext not in _SUPPORTED_EXTENSIONS:
        raise IngestException("unsupported_image_type", f"Unsupported image type '{ext}'.")

    _verify_image(path)
    return path


def _download_image(product_id: str, image_url: str, cache_dir: Path, timeout_s: float) -> Path:
    ext = _infer_extension(image_url)
    filename = _build_cached_filename(product_id, image_url, ext)
    destination = cache_dir / filename

    if destination.exists():
        _verify_image(destination)
        return destination

    try:
        response = requests.get(image_url, timeout=timeout_s)
        response.raise_for_status()
    except RequestException as exc:
        raise IngestException("network_error", f"Failed to download {image_url}: {exc}") from exc

    destination.write_bytes(response.content)

    try:
        _verify_image(destination)
    except IngestException:
        destination.unlink(missing_ok=True)
        raise

    return destination


def _verify_image(path: Path) -> None:
    try:
        with Image.open(path) as img:
            img.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise IngestException("decode_failure", f"Unable to decode image at {path}: {exc}") from exc


def _build_cached_filename(product_id: str, image_url: str, ext: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", product_id.lower()).strip("-") or "product"
    digest = hashlib.sha1(image_url.encode("utf-8"), usedforsecurity=False).hexdigest()[:10]
    return f"{slug}_{digest}{ext}"


def _infer_extension(image_url: str) -> str:
    path = Path(image_url.split("?", maxsplit=1)[0])
    ext = path.suffix.lower()
    if not ext:
        ext = ".jpg"
    if ext not in _SUPPORTED_EXTENSIONS:
        raise IngestException("unsupported_image_type", f"Unsupported image type '{ext}'.")
    return ext
