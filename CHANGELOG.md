# Changelog

## [v0.1.0] - 2026-01-27
- Initial MVP commit covering ingest → enrich → predict deterministic pipeline.
- FastAPI service with `/v1/enrich` + `/v1/predict` single and batch endpoints.
- Dockerfile, docker-compose, GitHub Actions CI, and Makefile helpers.
- Local publish/warehouse seams, contracts, docs, Terraform blueprint placeholders.
- Benchmark scripts (`make bench`, `make bench-api`) and Typer CLI demo command.
