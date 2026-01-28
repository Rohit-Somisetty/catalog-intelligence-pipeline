# Terraform Blueprint (Placeholder)

This directory is intentionally minimal and documents the resources that will back the production deployment. Copy these files into your infrastructure repository or extend them directly when you are ready to move beyond the local stubs.

## Resources covered
- **Pub/Sub topic** for `catalog_predictions` events.
- **BigQuery dataset + table** that matches `contracts/bigquery/catalog_predictions_bq_schema.json`.
- **Cloud Run service** that hosts the FastAPI container (see `docs/cloud_run.md`).
- **Service account + IAM bindings** for Pub/Sub publish and BigQuery write access.

> The `.tf` files only declare skeletons and variables so reviewers can see the shape of the infrastructure without unintentionally provisioning resources.
