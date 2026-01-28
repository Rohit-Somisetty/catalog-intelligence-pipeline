"""Typer CLI for running the catalog intelligence pipeline locally."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import typer
from pydantic import ValidationError

from .config import config
from .demo_utils import generate_synthetic_records
from .enrich import enrich_records
from .ingest import load_records, read_json_payload, resolve_images, write_jsonl
from .predict import predict_records
from .schemas import (
    EnrichedProductRecord,
    IngestedProductRecord,
    IngestError,
    PredictedProductRecord,
    RawProductRecord,
)
from .service_layer import predict_batch

app = typer.Typer(help="Run catalog attribute extraction workflows from the command line.")


@app.command()
def ingest(
    input_path: Path = typer.Argument(..., help="Path to raw catalog data (.json or .jsonl)."),
    out: Path = typer.Option(
        Path("data/ingested.jsonl"),
        "--out",
        "-o",
        help="Destination JSONL file for ingested payloads.",
    ),
    cache_dir: Path = typer.Option(
        Path(".cache/images"),
        "--cache-dir",
        help="Directory used to cache downloaded images.",
    ),
    errors_out: Path = typer.Option(
        Path("outputs/ingest_errors.jsonl"),
        "--errors-out",
        help="Path for persisting ingest errors in JSONL format.",
    ),
    timeout: float = typer.Option(10.0, help="HTTP timeout (seconds) for image downloads."),
    fail_fast: bool = typer.Option(False, "--fail-fast", help="Stop on the first ingest error.", is_flag=True),
) -> None:
    """Convert raw records into an ingested JSONL artifact with cached images."""

    raw_records = load_records(input_path)
    ingested_records, errors = resolve_images(
        raw_records,
        cache_dir=cache_dir,
        timeout_s=timeout,
        fail_fast=fail_fast,
    )

    write_jsonl(out, ingested_records)
    typer.echo(f"Wrote {len(ingested_records)} ingested record(s) → {out}")

    if errors:
        write_jsonl(errors_out, errors)
        typer.echo(f"Captured {len(errors)} ingest error(s) → {errors_out}")


@app.command()
def enrich(
    input_path: Path = typer.Argument(..., help="Path to ingested (.jsonl) or raw (.json/.jsonl) records."),
    out: Path = typer.Option(
        Path("outputs/enriched.jsonl"),
        "--out",
        "-o",
        help="Destination JSONL file for enriched payloads.",
    ),
    cache_dir: Path = typer.Option(
        Path(".cache/images"),
        "--cache-dir",
        help="Directory used to cache downloaded images when needed.",
    ),
    errors_out: Path = typer.Option(
        Path("outputs/ingest_errors.jsonl"),
        "--errors-out",
        help="Where to log ingest errors encountered during auto-ingest.",
    ),
    timeout: float = typer.Option(10.0, help="HTTP timeout (seconds) for image downloads."),
    fail_fast: bool = typer.Option(False, "--fail-fast", help="Stop on the first ingest error.", is_flag=True),
) -> None:
    """Run the enrichment stage to produce attribute predictions JSONL."""

    records, ingest_errors = _materialize_ingested_records(input_path, cache_dir, timeout, fail_fast)
    _persist_ingest_errors(ingest_errors, errors_out)

    if not records:
        typer.echo("No valid records available after ingestion.", err=True)
        raise typer.Exit(code=1)

    enriched = enrich_records(records)
    write_jsonl(out, enriched)
    typer.echo(f"Wrote {len(enriched)} enriched record(s) → {out}")


@app.command()
def predict(
    input_path: Path = typer.Argument(..., help="Path to raw/ingested/enriched records (.json/.jsonl)."),
    out: Path = typer.Option(
        Path("outputs/predicted.jsonl"),
        "--out",
        "-o",
        help="Destination JSONL file for fused predictions.",
    ),
    cache_dir: Path = typer.Option(
        Path(".cache/images"),
        "--cache-dir",
        help="Directory used to cache downloaded images when needed.",
    ),
    errors_out: Path = typer.Option(
        Path("outputs/ingest_errors.jsonl"),
        "--errors-out",
        help="Where to log ingest errors encountered during auto-ingest.",
    ),
    timeout: float = typer.Option(10.0, help="HTTP timeout (seconds) for image downloads."),
    fail_fast: bool = typer.Option(False, "--fail-fast", help="Stop on the first ingest error.", is_flag=True),
) -> None:
    """Run text enrichment + vision fusion and persist JSONL predictions."""

    enriched, ingest_errors = _ensure_enriched_records(input_path, cache_dir, timeout, fail_fast)
    _persist_ingest_errors(ingest_errors, errors_out)

    if not enriched:
        typer.echo("No enriched records available for prediction.", err=True)
        raise typer.Exit(code=1)

    predictions = predict_records(enriched)
    write_jsonl(out, predictions)
    typer.echo(f"Wrote {len(predictions)} prediction record(s) → {out}")


@app.command()
def run(
    input_path: Path = typer.Argument(
        ...,
        help="Path to raw (.json/.jsonl) or ingested (.jsonl) records.",
    ),
    output: Path = typer.Option(
        Path("outputs/predictions.json"),
        "--output",
        "-o",
        help="Location where the enriched JSON output will be written.",
    ),
    pretty: bool = typer.Option(True, help="Pretty-print JSON output with indentation."),
    cache_dir: Path = typer.Option(
        Path(".cache/images"),
        "--cache-dir",
        help="Directory used to cache downloaded images when needed.",
    ),
    errors_out: Path = typer.Option(
        Path("outputs/ingest_errors.jsonl"),
        "--errors-out",
        help="Where to log ingest errors encountered during auto-ingest.",
    ),
    timeout: float = typer.Option(10.0, help="HTTP timeout (seconds) for image downloads."),
    fail_fast: bool = typer.Option(False, "--fail-fast", help="Stop on the first ingest error.", is_flag=True),
) -> None:
    """Process catalog records, run enrichment, and write JSON array output."""

    enriched, ingest_errors = _ensure_enriched_records(input_path, cache_dir, timeout, fail_fast)
    _persist_ingest_errors(ingest_errors, errors_out)

    if not enriched:
        typer.echo("No enriched records available for prediction.", err=True)
        raise typer.Exit(code=1)

    predictions = predict_records(enriched)
    _write_json_output(output, predictions, pretty)
    typer.echo(f"Processed {len(predictions)} record(s) → {output}")


@app.command()
def demo(
    n: int = typer.Option(25, "--n", min=1, help="Number of synthetic records to process."),
    enable_publish: bool = typer.Option(
        True,
        help="Toggle local event publishing for the demo run.",
        show_default=True,
    ),
    enable_warehouse: bool = typer.Option(
        True,
        help="Toggle local DuckDB/CSV warehouse writes for the demo run.",
        show_default=True,
    ),
    output_dir: Path = typer.Option(
        Path("outputs/demo"),
        "--output-dir",
        help="Directory where demo artifacts will be written.",
    ),
) -> None:
    """Run an end-to-end demo with synthetic records + local outputs."""

    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    records = generate_synthetic_records(n, images_dir)

    ingested, ingest_errors = resolve_images(
        records,
        cache_dir=config.cache_dir,
        timeout_s=config.ingest_timeout_s,
        fail_fast=False,
    )
    if ingest_errors:
        errors_path = output_dir / "ingest_errors.jsonl"
        write_jsonl(errors_path, ingest_errors)
        typer.echo(f"Encountered {len(ingest_errors)} ingest warning(s) → {errors_path}")

    if not ingested:
        typer.echo("Demo aborted: no records ingested.", err=True)
        raise typer.Exit(code=1)

    enriched = enrich_records(ingested)
    enriched_path = output_dir / "enriched.jsonl"
    write_jsonl(enriched_path, enriched)

    demo_cfg = replace(
        config,
        enable_publish=enable_publish,
        publish_mode="local",
        enable_warehouse=enable_warehouse,
        warehouse_mode=config.warehouse_mode,
    )

    predictions, errors, _timings = predict_batch(enriched, demo_cfg)
    predicted_path = output_dir / "predicted.jsonl"
    write_jsonl(predicted_path, predictions)

    summary = [f"Demo processed {len(predictions)} record(s) (errors={len(errors)})."]
    summary.append(f"Enriched JSONL → {enriched_path}")
    summary.append(f"Predicted JSONL → {predicted_path}")
    if enable_publish:
        summary.append(f"Events → {demo_cfg.events_dir / 'catalog_predictions.jsonl'}")
    if enable_warehouse:
        summary.append(f"Warehouse → {demo_cfg.warehouse_path}")
    typer.echo("\n".join(summary))


def _load_payload(path: Path) -> list[dict[str, Any]]:
    return read_json_payload(path)


def _materialize_ingested_records(
    input_path: Path,
    cache_dir: Path,
    timeout: float,
    fail_fast: bool,
) -> tuple[list[IngestedProductRecord], list[IngestError]]:
    payload = _load_payload(input_path)
    if not payload:
        typer.echo("No records found in input.", err=True)
        return [], []
    return _prepare_records(payload, cache_dir, timeout, fail_fast)


def _prepare_records(
    payload: list[dict[str, Any]],
    cache_dir: Path,
    timeout: float,
    fail_fast: bool,
) -> tuple[list[IngestedProductRecord], list[IngestError]]:
    has_local_path = all(_has_local_path(item) for item in payload)
    any_local_path = any(_has_local_path(item) for item in payload)

    if any_local_path and not has_local_path:
        raise typer.BadParameter("Input mixes ingested and raw records; please use a consistent file.")

    if has_local_path:
        try:
            records = [IngestedProductRecord.model_validate(item) for item in payload]
        except ValidationError as exc:
            raise typer.BadParameter(f"Invalid ingested payload: {exc}") from exc
        return records, []

    raw_records = [RawProductRecord.model_validate(item) for item in payload]
    ingested_records, errors = resolve_images(
        raw_records,
        cache_dir=cache_dir,
        timeout_s=timeout,
        fail_fast=fail_fast,
    )
    return ingested_records, errors


def _has_local_path(item: dict[str, Any]) -> bool:
    value = item.get("image_local_path")
    return isinstance(value, str) and bool(value.strip())


def _persist_ingest_errors(errors: list[IngestError], destination: Path) -> None:
    if not errors:
        return
    write_jsonl(destination, errors)
    typer.echo(f"Encountered {len(errors)} ingest error(s). Details → {destination}", err=True)


def _write_json_output(path: Path, records: list[PredictedProductRecord], pretty: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    indent = 2 if pretty else None
    serialized = [record.model_dump(mode="json") for record in records]
    path.write_text(json.dumps(serialized, indent=indent), encoding="utf-8")


def _ensure_enriched_records(
    input_path: Path,
    cache_dir: Path,
    timeout: float,
    fail_fast: bool,
) -> tuple[list[EnrichedProductRecord], list[IngestError]]:
    payload = _load_payload(input_path)
    if not payload:
        return [], []

    if all("predictions" in item for item in payload):
        try:
            enriched = [EnrichedProductRecord.model_validate(item) for item in payload]
        except ValidationError as exc:
            raise typer.BadParameter(f"Invalid enriched payload: {exc}") from exc
        return enriched, []

    ingested, errors = _prepare_records(payload, cache_dir, timeout, fail_fast)
    if not ingested:
        return [], errors
    return enrich_records(ingested), errors


if __name__ == "__main__":
    app()
