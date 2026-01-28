PYTHON ?= python
SRC_DIR := src
TEST_DIR := tests

.PHONY: install lint test format typecheck run-api run-cli bench bench-api

install:
	$(PYTHON) -m pip install -e .[dev]

lint:
	ruff check $(SRC_DIR) $(TEST_DIR)
	mypy $(SRC_DIR) $(TEST_DIR)

format:
	ruff format $(SRC_DIR) $(TEST_DIR)

typecheck:
	mypy $(SRC_DIR) $(TEST_DIR)

test:
	pytest

run-api:
	uvicorn catalog_intelligence_pipeline.api:app --reload

run-cli:
	catalog-pipeline run data/sample_inputs.json --output outputs/predictions.json

bench:
	$(PYTHON) scripts/benchmark_predict.py

bench-api:
	$(PYTHON) scripts/benchmark_api.py
