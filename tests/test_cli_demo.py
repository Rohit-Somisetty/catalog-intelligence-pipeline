from __future__ import annotations

import importlib

from typer.testing import CliRunner

import catalog_intelligence_pipeline.cli as cli_module


def test_demo_command_runs(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    events_dir = tmp_path / "events"
    warehouse_path = tmp_path / "warehouse.duckdb"
    monkeypatch.setenv("CIP_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("CIP_EVENTS_DIR", str(events_dir))
    monkeypatch.setenv("CIP_WAREHOUSE_PATH", str(warehouse_path))

    cli = importlib.reload(cli_module)
    runner = CliRunner()
    output_dir = tmp_path / "demo"
    result = runner.invoke(
        cli.app,
        [
            "demo",
            "--n",
            "2",
            "--output-dir",
            str(output_dir),
            "--no-enable-publish",
            "--no-enable-warehouse",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (output_dir / "enriched.jsonl").exists()
    assert (output_dir / "predicted.jsonl").exists()
