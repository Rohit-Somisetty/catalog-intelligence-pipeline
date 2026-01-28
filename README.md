# Catalog Intelligence Pipeline (Vision + GenAI + GCP)

A Wayfair Catalog Intelligence reference implementation that ingests product records (image URL, title, description) and emits structured merchandising attributes. The system is locally runnable end-to-end, yet keeps clear seams for GCP services (Vision API, Vertex AI) while providing deterministic mocks for dev/test.

## Features
- **Multimodal pipeline** with typed contracts for ingestion → enrichment → vision inference → fusion.
- **FastAPI service** exposing `/health` plus versioned `/v1/enrich` + `/v1/predict` (single + batch) endpoints with structured errors and timing logs.
- **Typer CLI** offering `ingest`, `enrich`, `predict`, `run`, and `demo` workflows with image caching support.
- **Benchmarks + profiling helpers** so you can spot regressions locally before shipping.
- **Deterministic mock providers** (LLM + vision) so the system works offline without cloud credentials.
- **Decision logs** documenting which modality won each attribute and why.
- **Ruff + MyPy + Pytest** wired through the Makefile for linting, typing, and testing.

## Requirements
- Python 3.11+
- `pip` (or your preferred virtual environment manager)

## Installation
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

## Quickstart: Local
1. Inspect the toy payload in `data/sample_inputs.json`:
   ```json
   [
     {
       "product_id": "sample-001",
       "image_url": "https://example.com/images/walnut-dining-table.jpg",
       "title": "Walnut Dining Table",
       "description": "Mid-century modern dining table crafted from walnut. Measures 60 in x 36 in."
     }
   ]
   ```
2. Ingest and cache assets locally (writes `data/ingested.jsonl` + `.cache/images/`):
   ```bash
   catalog-pipeline ingest data/sample_inputs.json --out data/ingested.jsonl
   ```
3. Run the deterministic enrichment stage to derive structured text attributes:
   ```bash
   catalog-pipeline enrich data/ingested.jsonl --out outputs/enriched.jsonl
   ```
4. Fuse text + vision signals to produce final predictions (JSONL):
   ```bash
   catalog-pipeline predict data/ingested.jsonl --out outputs/predicted.jsonl
   ```
5. Or run the helper that accepts raw JSON and returns a JSON array:
   ```bash
   catalog-pipeline run data/sample_inputs.json --output outputs/predicted.json
   ```
6. Example prediction record (trimmed):
   ```json
   {
     "product_id": "sample-001",
     "title": "Walnut Dining Table",
     "final_predictions": {
       "category": {"value": "Table", "confidence": 0.88, "extracted_by": "fusion", "evidence": ["Walnut Dining Table", "vision label: Table (table)"]},
       "room_type": {"value": "Dining Room", "confidence": 0.95, "extracted_by": "fusion", "evidence": ["dining table crafted from walnut"]},
       "style": {"value": "Mid-Century", "confidence": 0.9, "extracted_by": "llm_stub", "evidence": ["Mid-century modern dining table"]},
       "material": {"value": "Walnut", "confidence": 0.75, "extracted_by": "llm_stub", "evidence": ["walnut"]}
     },
     "decision_log": {
       "category": {"sources_considered": ["text", "vision"], "chosen_source": "merged", "reason": "Text and vision agreed on the attribute value.", "conflicts": []}
     }
   }
   ```

## Demo Run (one command)
Spin up a deterministic dataset, run ingest → enrich → predict, and capture optional event/warehouse artifacts without touching environment variables:

```bash
catalog-pipeline demo --n 25
```

- Artifacts land in `outputs/demo/` (`enriched.jsonl`, `predicted.jsonl`, and `ingest_errors.jsonl` when needed).
- Local publish + warehouse seams are enabled by default for the demo; disable via `--no-enable-publish` / `--no-enable-warehouse`.
- Events append to `outputs/events/catalog_predictions.jsonl`, while DuckDB rows land in `outputs/warehouse.duckdb` unless you override the standard CIP env vars.

## Services & Commands
- Run ingestion only (JSON/JSONL → JSONL + cached images):
  ```bash
  catalog-pipeline ingest data/sample_inputs.json --out data/ingested.jsonl --cache-dir .cache/images
  ```
- Run the deterministic enrichment stage (JSON/JSONL → enriched JSONL):
  ```bash
  catalog-pipeline enrich data/ingested.jsonl --out outputs/enriched.jsonl
  ```
- Run fused prediction stage (text + vision → JSONL):
  ```bash
  catalog-pipeline predict data/ingested.jsonl --out outputs/predicted.jsonl
  ```
- Run the FastAPI server:
  ```bash
  uvicorn catalog_intelligence_pipeline.api:app --reload
  ```
- REST API endpoints (JSON in/out):
  - `GET /health` – readiness probe.
  - `POST /v1/enrich` – single record → `EnrichedProductRecord`.
  - `POST /v1/enrich/batch` – `{ "items": [...] }` with successes + indexed errors.
  - `POST /v1/predict` – single record (raw/ingested/enriched) → fused predictions.
  - `POST /v1/predict/batch` – batch fusion while surfacing per-record failures.
  - `POST /predict` – **deprecated**, proxies to the v1 predict handler.

### API Examples

Single prediction:
```bash
curl -X POST http://localhost:8000/v1/predict \
  -H "Content-Type: application/json" \
  -d '{
        "product_id": "sample-001",
        "title": "Walnut Dining Table",
        "description": "Mid-century dining table.",
        "image_url": "https://example.com/images/walnut-table.jpg"
      }'
```

Batch prediction with graceful error handling:
```bash
curl -X POST http://localhost:8000/v1/predict/batch \
  -H "Content-Type: application/json" \
  -d '{
        "items": [
          {
            "product_id": "sample-002",
            "title": "Velvet Sofa",
            "description": "Plush velvet 3-seater",
            "image_url": "https://example.com/images/velvet-sofa.jpg"
          },
          {
            "product_id": "sample-003",
            "title": "Broken Image",
            "description": "Intentional failure",
            "image_url": "https://example.com/missing.jpg"
          }
        ]
      }'
```
Responses contain `items` (successes) and `errors` with `{index, product_id, stage, ...}` entries when a record fails ingest/enrich/predict.

## Performance Benchmarks
- Direct pipeline benchmark (no HTTP) to measure stage timings via `service_layer.predict_batch`:
  ```bash
  make bench  # wraps [scripts/benchmark_predict.py](scripts/benchmark_predict.py)
  ```
  Produces `outputs/benchmarks/benchmark.json` containing total runtime, per-record avg/p50/p95, and ingest/enrich/vision/fuse breakdowns.
- HTTP benchmark (requires the API to be running locally):
  ```bash
  uvicorn catalog_intelligence_pipeline.api:app --reload &
  make bench-api  # wraps [scripts/benchmark_api.py](scripts/benchmark_api.py)
  ```
  Uses `httpx` with configurable concurrency to stress `/v1/predict/batch`, emitting p50/p95 latencies plus request-level error rate.

Both scripts rely on the lightweight timing helper in [src/catalog_intelligence_pipeline/timing.py](src/catalog_intelligence_pipeline/timing.py) and the deterministic payload generator in [src/catalog_intelligence_pipeline/demo_utils.py](src/catalog_intelligence_pipeline/demo_utils.py).

## API Limits & Safety
The FastAPI layer enforces guardrails before doing any IO:

- **Batch size** – defaults to 50 items/request (`CIP_MAX_BATCH_ITEMS`). Larger payloads yield HTTP 413 with `batch_limit_exceeded`.
- **Text size** – combined `title + description` capped at 10k chars (`CIP_MAX_TEXT_CHARS`). Violations return HTTP 413 with `text_limit_exceeded`.
- **Rate limiting** – simple in-process token bucket defaults to 120 requests/min (`CIP_RPM_LIMIT`). When exhausted, requests see HTTP 429 + `rate_limited`.
- **Timeouts** – ingestion downloads still obey `CIP_INGEST_TIMEOUT_S`; additionally, the service layer now aborts any record that exceeds `CIP_RECORD_TIMEOUT_S` (8s default) with `error_type="timeout"` and stage metadata.

Adjust the env vars above to tune the limits for your environment.

## Production Readiness
- **Docker image** (FastAPI + UVicorn):
  ```bash
  docker build -t catalog-intel-api .
  docker run --rm -p 8000:8000 \
    -e CIP_CACHE_DIR=/app/.cache/images \
    catalog-intel-api
  ```
- **Docker Compose** with live-reload + local cache:
  ```bash
  docker-compose up --build
  ```
- **CI/CD**: `.github/workflows/ci.yml` installs the project (dev extras) and runs `make lint` + `make test` on every push/PR.

## Event & Warehouse Outputs (Local mode)
Enable the optional publish + sink behavior by toggling env vars before running the API/CLI:

```bash
export CIP_ENABLE_PUBLISH=1
export CIP_PUBLISH_MODE=local
export CIP_EVENTS_DIR=outputs/events
export CIP_ENABLE_WAREHOUSE=1
export CIP_WAREHOUSE_MODE=duckdb   # or csv
export CIP_WAREHOUSE_PATH=outputs/warehouse.duckdb
export CIP_VALIDATE_EVENTS=1
uvicorn catalog_intelligence_pipeline.api:app --reload
```

- Events are appended to `outputs/events/catalog_predictions.jsonl` via the local publisher seam.
- Warehouse rows are flattened (see `src/catalog_intelligence_pipeline/flatten.py`) and flushed to DuckDB/CSV using the sinks under `gcp_seams/`.
- JSON Schema + BigQuery schemas live under `contracts/` and power optional runtime validation.

## Makefile Targets
- `make install` – Install the project in editable mode with dev dependencies.
- `make lint` – Run Ruff (style) and MyPy (types).
- `make test` – Execute Pytest suites.
- `make run-api` – Launch FastAPI with Uvicorn (reload on changes).
- `make run-cli` – Process the sample payload via Typer CLI.
- `make bench` – Run the local service-layer benchmark (writes `outputs/benchmarks/benchmark.json`).
- `make bench-api` – Fire the HTTP benchmark (expects the API to be running locally).

## GCP Production Blueprint
- **Architecture overview**: see [docs/architecture.md](docs/architecture.md) for the Pub/Sub → Dataflow/Cloud Run Jobs → BigQuery pathway, plus optional GCS + Vertex AI touchpoints.
- **Cloud Run deployment guide**: [docs/cloud_run.md](docs/cloud_run.md) outlines the container build, `gcloud run deploy` commands, recommended resources, and required env vars.
- **Contracts**: JSON Schema + BigQuery definitions live under [contracts/](contracts). Enable `CIP_VALIDATE_EVENTS=1` to enforce the schema before publishing.
- **Infra placeholders**: [infra/terraform](infra/terraform/README.md) contains Terraform skeletons for topics, datasets, Cloud Run, and future IAM bindings.
- **Provider seams**: swap in real Pub/Sub + BigQuery clients inside `gcp_seams/` once production credentials are available; the rest of the pipeline remains unchanged.

## Project Structure
```
.
├── data/
│   └── sample_inputs.json
├── src/
│   └── catalog_intelligence_pipeline/
│       ├── api.py
│       ├── cli.py
│       ├── contracts.py
│       ├── config.py
│       ├── flatten.py
│       ├── enrich.py
│       ├── fusion.py
│       ├── ingest.py
│       ├── gcp_seams/
│       │   ├── __init__.py
│       │   ├── publishers.py
│       │   └── warehouse.py
│       ├── pipeline.py
│       ├── predict.py
│       ├── service_layer.py
│       ├── schemas.py
│       ├── extractors/
│       │   ├── __init__.py
│       │   ├── dimensions.py
│       │   ├── text_attributes.py
│       │   └── vision_attributes.py
│       └── providers/
│           ├── __init__.py
│           ├── llm.py
│           └── vision.py
├── tests/
│   ├── test_api.py
│   ├── test_contracts.py
│   ├── test_flatten.py
│   ├── test_fusion.py
│   ├── test_publishers.py
│   ├── test_predict.py
│   ├── test_pipeline.py
│   ├── test_service_layer_outputs.py
│   └── test_vision.py
├── docs/
│   ├── architecture.md
│   └── cloud_run.md
├── contracts/
│   ├── pubsub_catalog_predictions.schema.json
│   ├── examples/
│   └── bigquery/
├── infra/
│   └── terraform/
│       ├── README.md
│       ├── main.tf
│       ├── outputs.tf
│       └── variables.tf
├── Makefile
├── pyproject.toml
└── README.md
```

## Next Steps
- Swap the deterministic mocks with GCP implementations (Vision API for images, Vertex AI / PaLM for text) using the existing provider interfaces.
- Expand attribute coverage (styles, finishes, dimensions) plus add slice-aware evaluation harnesses.
