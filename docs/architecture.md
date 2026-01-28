# Catalog Intelligence – GCP Reference Architecture

The diagram below captures the long-term deployment target. The current repository ships local-first mocks and stubs while keeping the critical seams ready for GCP clients.

```mermaid
flowchart LR
    Client((Client / Partner API Caller)) -->|HTTPS JSON| CloudRun[(Cloud Run API)]
    CloudRun -->|Pub/Sub event| PubSub[(Pub/Sub Topic\ncatalog_predictions)]
    PubSub --> Dataflow[[Dataflow / Cloud Run Jobs\n(Batch Enrichment)]]
    Dataflow --> BigQuery[(BigQuery Dataset\ncatalog.predictions)]
    CloudRun -->|Image fetch| GCS[(GCS Image Bucket)]
    CloudRun -->|Future Models| VertexAI[(Vertex AI Hosted Models)]
```

**Flow summary**

1. Clients post `/v1/predict` to the Cloud Run API (container in this repo).
2. The API publishes `catalog_predictions` events to Pub/Sub and simultaneously flushes flattened rows to BigQuery (today mocked via local DuckDB/CSV sinks).
3. Downstream Dataflow or Cloud Run Jobs can subscribe to the topic for further processing (e.g., metric aggregation, content review).
4. Optional storage services (GCS for cached media, Vertex AI for real models) plug into the provider seams already defined in `providers/` and `gcp_seams/`.
