from __future__ import annotations

import json
from pathlib import Path

from catalog_intelligence_pipeline.gcp_seams.publishers import LocalFilePublisher


def test_local_file_publisher_writes_jsonl(tmp_path: Path) -> None:
    publisher = LocalFilePublisher(tmp_path)
    payload = {"event_id": "abc", "value": 1}

    message_id_1 = publisher.publish("catalog_predictions", payload)
    message_id_2 = publisher.publish("catalog_predictions", payload)

    assert message_id_1 == message_id_2  # deterministic hash

    topic_file = tmp_path / "catalog_predictions.jsonl"
    lines = topic_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == payload
