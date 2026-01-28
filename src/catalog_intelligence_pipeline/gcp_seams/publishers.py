"""Pub/Sub publisher seams for local development and future GCP integration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Protocol


class Publisher(Protocol):
    """Minimal interface required by the prediction pipeline."""

    def publish(self, topic: str, message: dict[str, Any]) -> str:  # pragma: no cover - Protocol
        """Publish a message to a topic and return the message identifier."""


class LocalFilePublisher:
    """Writes Pub/Sub-style events to topic-scoped JSONL files for inspection."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def publish(self, topic: str, message: dict[str, Any]) -> str:
        payload = json.dumps(message, sort_keys=True)
        message_id = hashlib.sha1(payload.encode("utf-8"), usedforsecurity=False).hexdigest()
        topic_file = self._base_dir / f"{topic}.jsonl"
        topic_file.parent.mkdir(parents=True, exist_ok=True)
        with topic_file.open("a", encoding="utf-8") as handle:
            handle.write(payload)
            handle.write("\n")
        return message_id


class StubPubSubPublisher:
    """Placeholder that documents how to wire the real google-cloud-pubsub client."""

    def publish(self, topic: str, message: dict[str, Any]) -> str:  # pragma: no cover - explicit failure
        raise NotImplementedError(
            "Stub publisher invoked. Replace with google-cloud-pubsub PublisherClient.publish(...)"
        )
