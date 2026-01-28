variable "project_id" {
  description = "GCP project hosting the stack"
  type        = string
}

variable "region" {
  description = "Primary region for Cloud Run and Pub/Sub"
  type        = string
  default     = "us-central1"
}

variable "pubsub_topic_name" {
  description = "Pub/Sub topic for catalog prediction events"
  type        = string
  default     = "catalog_predictions"
}

variable "bigquery_dataset" {
  description = "BigQuery dataset id (e.g., catalog)"
  type        = string
  default     = "catalog"
}

variable "bigquery_table" {
  description = "BigQuery table id"
  type        = string
  default     = "catalog_predictions"
}

variable "bigquery_location" {
  description = "BigQuery dataset location"
  type        = string
  default     = "US"
}

variable "cloud_run_name" {
  description = "Cloud Run service name"
  type        = string
  default     = "catalog-intel-api"
}

variable "cloud_run_image" {
  description = "Container image URI"
  type        = string
}

variable "enable_publish" {
  description = "Whether the API should publish Pub/Sub events"
  type        = string
  default     = "1"
}

variable "enable_warehouse" {
  description = "Whether the API should write to the warehouse sink"
  type        = string
  default     = "1"
}
