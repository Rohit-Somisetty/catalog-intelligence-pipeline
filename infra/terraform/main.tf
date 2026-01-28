terraform {
  required_version = ">= 1.7.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Pub/Sub Topic (placeholder)
resource "google_pubsub_topic" "catalog_predictions" {
  name = var.pubsub_topic_name
  labels = {
    service = "catalog-intel"
  }
}

# BigQuery dataset + table placeholders (schema kept under contracts/bigquery)
resource "google_bigquery_dataset" "catalog" {
  dataset_id                  = var.bigquery_dataset
  friendly_name               = "Catalog Intelligence"
  location                    = var.bigquery_location
  delete_contents_on_destroy  = false
}

resource "google_bigquery_table" "catalog_predictions" {
  dataset_id = google_bigquery_dataset.catalog.dataset_id
  table_id   = var.bigquery_table
  schema     = file("${path.module}/../../contracts/bigquery/catalog_predictions_bq_schema.json")
}

# Cloud Run service placeholder – wire the Docker image built from this repo.
resource "google_cloud_run_service" "api" {
  name     = var.cloud_run_name
  location = var.region

  template {
    spec {
      containers {
        image = var.cloud_run_image
        env {
          name  = "CIP_ENABLE_PUBLISH"
          value = var.enable_publish
        }
        env {
          name  = "CIP_ENABLE_WAREHOUSE"
          value = var.enable_warehouse
        }
      }
    }
  }
}

# Service account + IAM bindings would be added here.
