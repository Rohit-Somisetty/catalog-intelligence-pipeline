"""Warehouse sink seams for BigQuery and local development targets."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Protocol

import duckdb


class WarehouseSink(Protocol):
    """Minimal interface for writing tabular prediction rows."""

    def write_table(self, dataset: str, table: str, rows: list[dict[str, Any]]) -> None:  # pragma: no cover
        ...


class LocalCSVSink:
    """Persists flattened rows to dataset.table CSV files for quick inspection."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def write_table(self, dataset: str, table: str, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return

        destination = self._base_dir / f"{dataset}.{table}.csv"
        destination.parent.mkdir(parents=True, exist_ok=True)
        write_header = not destination.exists()
        fieldnames = list(rows[0].keys())

        with destination.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            for row in rows:
                writer.writerow({key: _serialize_value(value) for key, value in row.items()})


class LocalDuckDBSink:
    """Stores flattened rows inside a DuckDB file to mimic BigQuery schemas."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    def write_table(self, dataset: str, table: str, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return

        table_name = _normalize_name(dataset, table)
        columns = list(rows[0].keys())
        conn = duckdb.connect(str(self._db_path))
        try:
            self._ensure_table(conn, table_name, columns, rows[0])
            placeholders = ", ".join(["?"] * len(columns))
            col_clause = ", ".join(columns)
            insert_sql = f"INSERT INTO {table_name} ({col_clause}) VALUES ({placeholders})"
            for row in rows:
                values = [row.get(column) for column in columns]
                conn.execute(insert_sql, values)
        finally:
            conn.close()

    def _ensure_table(
        self,
        conn: duckdb.DuckDBPyConnection,
        table_name: str,
        columns: list[str],
        sample_row: dict[str, Any],
    ) -> None:
        column_defs = []
        for column in columns:
            column_type = _infer_column_type(column, sample_row.get(column))
            column_defs.append(f"{column} {column_type}")
        definition = ", ".join(column_defs)
        conn.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({definition})")


class StubBigQuerySink:
    """Placeholder that documents where to plug BigQuery client logic."""

    def write_table(self, dataset: str, table: str, rows: list[dict[str, Any]]) -> None:  # pragma: no cover
        raise NotImplementedError(
            "Stub sink invoked. Replace with google-cloud-bigquery Table.insert_rows_json(...)"
        )


def _serialize_value(value: Any) -> Any:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _normalize_name(dataset: str, table: str) -> str:
    safe_dataset = dataset.replace("-", "_").replace(".", "_")
    safe_table = table.replace("-", "_").replace(".", "_")
    return f"{safe_dataset}__{safe_table}"


_NUMERIC_COLUMNS = {
    "category_confidence",
    "room_type_confidence",
    "style_confidence",
    "material_confidence",
}


def _infer_column_type(column: str, value: Any) -> str:
    if column == "event_ts":
        return "TIMESTAMP"
    if column in _NUMERIC_COLUMNS:
        return "DOUBLE"
    if isinstance(value, (int, float)):
        return "DOUBLE"
    return "VARCHAR"
