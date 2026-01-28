#!/usr/bin/env python
"""HTTP benchmark that drives the running FastAPI predict endpoint."""

from __future__ import annotations

import argparse
import asyncio
import math
from pathlib import Path
from time import perf_counter
from typing import List, Sequence, Tuple

import httpx

from catalog_intelligence_pipeline.demo_utils import generate_synthetic_records


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
    parser = argparse.ArgumentParser(description="Benchmark the /v1/predict/batch API endpoint.")
    parser.add_argument("--n", type=int, default=100, help="Total records to send.")
    parser.add_argument("--batch-size", type=int, default=10, help="Records per HTTP request.")
    parser.add_argument("--concurrency", type=int, default=4, help="Concurrent in-flight requests.")
    parser.add_argument("--url", type=str, default="http://127.0.0.1:8000/v1/predict/batch", help="Target batch endpoint.")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP client timeout in seconds.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for synthetic payloads.")
    return parser.parse_args()


def chunk(items: Sequence[dict], size: int) -> List[List[dict]]:
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


def to_payloads(records) -> List[dict]:
    payloads: List[dict] = []
    for record in records:
        payload = record.model_dump(mode="json")
        if record.image_path:
            payload["image_path"] = str(Path(record.image_path).resolve())
        payloads.append(payload)
    return payloads


async def post_batch(client: httpx.AsyncClient, url: str, batch: List[dict], sem: asyncio.Semaphore) -> Tuple[float, bool]:
    async with sem:
        start = perf_counter()
        try:
            response = await client.post(url, json={"items": batch})
            latency_ms = (perf_counter() - start) * 1000
            return latency_ms, response.status_code == 200
        except httpx.HTTPError:
            return (perf_counter() - start) * 1000, False


async def main_async(args: argparse.Namespace) -> None:
    images_dir = Path("outputs/benchmarks/api_images")
    records = generate_synthetic_records(args.n, images_dir, seed=args.seed)
    payloads = to_payloads(records)
    batches = chunk(payloads, args.batch_size)

    async with httpx.AsyncClient(timeout=args.timeout) as client:
        health_url = _derive_health_url(args.url)
        health = await client.get(health_url)
        if health.status_code != 200:
            raise RuntimeError("API health check failed.")

        sem = asyncio.Semaphore(max(1, args.concurrency))
        tasks = [post_batch(client, args.url, batch, sem) for batch in batches]
        results = await asyncio.gather(*tasks)

    latencies = [lat for lat, success in results if success]
    total_requests = len(results)
    errors = sum(0 if success else 1 for _, success in results)
    error_rate = errors / total_requests if total_requests else 0.0

    p50 = percentile(latencies, 0.5)
    p95 = percentile(latencies, 0.95)

    print(
        f"API benchmark (requests={total_requests}, concurrency={args.concurrency}) "
        f"p50={p50:.2f}ms p95={p95:.2f}ms error_rate={error_rate:.2%}"
    )


def _derive_health_url(predict_url: str) -> str:
    if "/v1/predict/batch" in predict_url:
        base = predict_url.rsplit("/v1/predict/batch", 1)[0]
    else:
        base = predict_url.rstrip("/")
    return f"{base}/health"


def main() -> None:
    args = parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
