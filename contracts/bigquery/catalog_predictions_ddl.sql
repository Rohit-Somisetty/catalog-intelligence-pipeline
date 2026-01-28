CREATE TABLE IF NOT EXISTS `catalog.catalog_predictions` (
  event_id STRING NOT NULL,
  event_ts TIMESTAMP NOT NULL,
  product_id STRING NOT NULL,
  category_value STRING,
  category_confidence FLOAT64,
  room_type_value STRING,
  room_type_confidence FLOAT64,
  style_value STRING,
  style_confidence FLOAT64,
  material_value STRING,
  material_confidence FLOAT64,
  raw_payload JSON
);
