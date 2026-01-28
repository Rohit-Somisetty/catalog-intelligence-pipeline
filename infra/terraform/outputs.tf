output "pubsub_topic" {
  description = "Pub/Sub topic name"
  value       = google_pubsub_topic.catalog_predictions.name
}

output "bigquery_table" {
  description = "Fully qualified BigQuery table"
  value       = "${google_bigquery_dataset.catalog.dataset_id}.${google_bigquery_table.catalog_predictions.table_id}"
}

output "cloud_run_service" {
  description = "Deployed Cloud Run service"
  value       = google_cloud_run_service.api.name
}
