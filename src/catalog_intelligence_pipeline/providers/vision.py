"""Vision provider interfaces and deterministic mocks."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod

from ..schemas import VisionLabel, VisionPrediction, VisionQualityFlags

_DEFAULT_LABELS = [
    "sofa",
    "sectional",
    "bed",
    "table",
    "chair",
    "lamp",
    "dresser",
    "rug",
    "desk",
    "bench",
]


class VisionProvider(ABC):
    """Interface for models that transform images into textual hints and labels."""

    @abstractmethod
    def describe(self, image_url: str) -> str:
        """Return a short textual summary given an image URL."""

    @abstractmethod
    def predict(self, image_local_path: str) -> VisionPrediction:
        """Return deterministic labels and quality metadata for an image."""


class MockVisionProvider(VisionProvider):
    """Deterministic mock vision provider for offline development."""

    _KEYWORD_HINTS: dict[str, str] = {
        "sofa": "Appears to be an upholstered sofa with neutral fabric.",
        "chair": "Looks like a single chair shot against a white backdrop.",
        "table": "A wooden table surface with clean lines is visible.",
        "lamp": "A standing lamp with a cylindrical shade is shown.",
        "bed": "An angled view of a neatly staged bed is visible.",
    }

    def describe(self, image_url: str) -> str:
        slug = image_url.lower()
        for keyword, hint in self._KEYWORD_HINTS.items():
            if keyword in slug:
                return hint
        return "Generic catalog image with minimal visual cues."

    def predict(self, image_local_path: str) -> VisionPrediction:
        digest = hashlib.sha1(image_local_path.encode("utf-8"), usedforsecurity=False).hexdigest()
        base_int = int(digest[:8], 16)
        confidence_seed = int(digest[8:16], 16)

        labels = self._select_labels(base_int, confidence_seed)
        quality_flags = self._build_quality_flags(base_int)
        trace_id = digest[:12]
        return VisionPrediction(labels=labels, quality_flags=quality_flags, trace_id=trace_id)

    def _select_labels(self, base_int: int, confidence_seed: int) -> list[VisionLabel]:
        labels: list[VisionLabel] = []
        total_labels = len(_DEFAULT_LABELS)
        for idx in range(3):
            label_index = (base_int + idx * 5) % total_labels
            raw = (confidence_seed >> (idx * 5)) & 0xFF
            confidence = 0.55 + (raw % 40) / 100  # 0.55 - 0.95
            confidence = min(confidence, 0.92)
            labels.append(VisionLabel(name=_DEFAULT_LABELS[label_index], confidence=confidence))
        return labels

    def _build_quality_flags(self, base_int: int) -> VisionQualityFlags:
        blurry = bool(base_int & 0x1)
        low_res = bool(base_int & 0x2)
        dark = bool(base_int & 0x4)
        return VisionQualityFlags(blurry=blurry, low_res=low_res, dark=dark)
