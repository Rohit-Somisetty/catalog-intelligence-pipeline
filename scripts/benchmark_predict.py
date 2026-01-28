#!/usr/bin/env python
"""Local benchmark for direct predict() pipeline execution."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import List

from catalog_intelligence_pipeline.config import config
from catalog_intelligence_pipeline.demo_utils import generate_synthetic_records
from catalog_intelligence_pipeline.ingest import resolve_images
from catalog_intelligence_pipeline.service_layer import predict_batch, summarize_timings
from catalog_intelligence_pipeline.timing import TimingTracker


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = pct * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[int(position)]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark catalog predict pipeline locally.")
    parser.add_argument("--n", type=int, default=100, help="Number of synthetic records to benchmark.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/benchmarks/benchmark.json"),
        help="Path where benchmark metrics JSON will be written.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for synthetic generation.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tracker = TimingTracker()
    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    images_dir = output_path.parent / "images"

    with tracker.context("generate_records"):
        records = generate_synthetic_records(args.n, images_dir, seed=args.seed)

    with tracker.context("ingest"):
        ingested, ingest_errors = resolve_images(
            records,
            cache_dir=config.cache_dir,
            timeout_s=config.ingest_timeout_s,
            fail_fast=False,
        )

    demo_cfg = replace(
        config,
        enable_publish=False,
        enable_warehouse=False,
    )

    start = perf_counter()
    with tracker.context("predict_batch"):
        predictions, errors, timings = predict_batch(ingested, demo_cfg)
    total_ms = (perf_counter() - start) * 1000

    per_record = [item.total_ms for item in timings]
    avg_ms = sum(per_record) / len(per_record) if per_record else 0.0
    p50 = percentile(per_record, 0.5)
    p95 = percentile(per_record, 0.95)
    breakdown = summarize_timings(timings)

    payload = {
        "records_requested": args.n,
        "records_completed": len(predictions),
        "ingest_errors": len(ingest_errors),
        "pipeline_errors": len(errors),
        "total_ms": total_ms,
        "per_record_ms": {"avg": avg_ms, "p50": p50, "p95": p95},
        "breakdown_ms": {
            "ingest_ms": breakdown.ingest_ms,
            "enrich_ms": breakdown.enrich_ms,
            "vision_ms": breakdown.vision_ms,
            "fuse_ms": breakdown.fuse_ms,
        },
        "script_timings_ms": tracker.as_dict(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Benchmark complete → {output_path}")
    print(
        f"Per-record avg={avg_ms:.2f}ms p50={p50:.2f}ms p95={p95:.2f}ms | "
        f"Breakdown ingest={breakdown.ingest_ms:.2f}ms enrich={breakdown.enrich_ms:.2f}ms "
        f"vision={breakdown.vision_ms:.2f}ms fuse={breakdown.fuse_ms:.2f}ms"
    )


if __name__ == "__main__":
    main()
