# Deploying the Catalog Intelligence API to Cloud Run (Blueprint)

These steps document the intended production workflow. They do **not** create any resources automatically but provide a cookbook for Platform/SRE teams.

## 1. Build and push the container image

```bash
PROJECT_ID="my-gcp-project"
REGION="us-central1"
IMAGE="catalog-intel-api"

# Build locally using the Dockerfile shipped with this repo
docker build -t gcr.io/${PROJECT_ID}/${IMAGE}:latest .

# Or use Cloud Build for reproducible builds
gcloud builds submit --tag gcr.io/${PROJECT_ID}/${IMAGE}:latest
```

## 2. Deploy to Cloud Run (fully managed)

```bash
gcloud run deploy catalog-intel-api \
  --image gcr.io/${PROJECT_ID}/${IMAGE}:latest \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 2 \
  --max-instances 20 \
  --concurrency 40 \
  --set-env-vars "CIP_CACHE_DIR=/tmp/cache" \
  --set-env-vars "CIP_EVENTS_DIR=/tmp/events" \
  --set-env-vars "CIP_PUBLISH_MODE=stub" \
  --set-env-vars "CIP_WAREHOUSE_MODE=stub" \
  --set-env-vars "CIP_ENABLE_PUBLISH=1" \
  --set-env-vars "CIP_ENABLE_WAREHOUSE=1" \
  --set-env-vars "CIP_VALIDATE_EVENTS=1"
```

### Recommended runtime settings
- **CPU / Memory**: 2 vCPU + 1GiB keeps ingestion + fusion responsive. Increase when using real ML backends.
- **Concurrency**: 40 requests per container balances latency vs. cost for typical 1–2s inference workloads.
- **Timeout**: Keep the default 300s unless downstream providers introduce longer waits.

### Networking considerations
- Allow egress to any domains hosting product images (`image_url`). In locked-down environments, proxy image fetches through a VPC-SC compliant service or pre-stage assets in GCS.
- Vertex AI / other managed services will need the Cloud Run service account to have `roles/aiplatform.user` once real models are enabled.

### Environment variables
| Variable | Purpose |
| --- | --- |
| `CIP_CACHE_DIR` | Local directory for downloaded images inside the container. Use `/tmp` or an in-memory volume. |
| `CIP_EVENTS_DIR` | Scratch space when using the local publisher (helpful for troubleshooting). |
| `CIP_ENABLE_PUBLISH` | Set to `1` (true) to publish Pub/Sub events. In production this should be paired with the real publisher implementation. |
| `CIP_ENABLE_WAREHOUSE` | Set to `1` to emit flattened rows to the warehouse sink. |
| `CIP_PUBLISH_MODE` | `local` (JSONL) or `stub` (placeholder for google-cloud-pubsub). |
| `CIP_WAREHOUSE_MODE` | `duckdb`, `csv`, or `stub`. |
| `CIP_VALIDATE_EVENTS` | When `1`, events are validated against `contracts/pubsub_catalog_predictions.schema.json` before publish. |

## 3. Grant service accounts
- **Pub/Sub**: `roles/pubsub.publisher` on the target topic.
- **BigQuery**: `roles/bigquery.dataEditor` on the dataset.
- **GCS image bucket (optional)**: `roles/storage.objectViewer`.

## 4. Observability hooks
- Structured logs already emit per-request timings. Export them to Cloud Logging and connect Cloud Monitoring dashboards/alerts as needed.
- Pub/Sub and BigQuery each provide message insert metrics; once real clients replace the stubs, wire alerts for delivery failures or insert errors.

> **Reminder:** This blueprint keeps everything infrastructure-as-code-friendly by placing Terraform/YAML stubs under `infra/`. Update them as you promote from local mode to real GCP clients.
