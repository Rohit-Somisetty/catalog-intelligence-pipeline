"""Language/LLM provider interfaces and deterministic mocks."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..extractors import extract_text_attributes
from ..schemas import AttributePrediction, AttributeResult, CoreAttributes, ProductRecord


class LLMProvider(ABC):
    """Interface for large-language-model based attribute extraction."""

    @abstractmethod
    def classify(self, record: ProductRecord, vision_hint: str) -> CoreAttributes:
        """Return structured attributes for a given product."""


class MockLLMProvider(LLMProvider):
    """Heuristic implementation that emulates a deterministic LLM."""

    def classify(self, record: ProductRecord, vision_hint: str) -> CoreAttributes:
        predictions = extract_text_attributes(record.title, record.description)
        category = self._convert_prediction(predictions["category"], "Decor")
        room = self._convert_prediction(predictions["room_type"], "Flexible Space")
        style = self._convert_prediction(predictions["style"], "Contemporary")
        material = self._convert_prediction(predictions["material"], "Mixed Materials")
        return CoreAttributes(
            category=category,
            room_type=room,
            style=style,
            material=material,
        )

    @staticmethod
    def _convert_prediction(prediction: AttributePrediction, fallback: str) -> AttributeResult:
        value = prediction.value if isinstance(prediction.value, str) else fallback
        rationale = "; ".join(prediction.evidence) if prediction.evidence else f"Derived by {prediction.extracted_by}."
        confidence = prediction.confidence if isinstance(prediction.value, str) else 0.5
        return AttributeResult(value=value, confidence=confidence, rationale=rationale)
