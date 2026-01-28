"""Pipeline orchestration that coordinates providers and data models."""

from __future__ import annotations

from datetime import UTC, datetime

from .extractors import extract_dimensions_prediction
from .providers import LLMProvider, MockLLMProvider, MockVisionProvider, VisionProvider
from .schemas import (
    AttributeResult,
    CatalogAttributes,
    CoreAttributes,
    ExtractedDimensions,
    PipelineResponse,
    ProductRecord,
)


class CatalogPipeline:
    """Coordinates providers to generate structured catalog intelligence outputs."""

    def __init__(self, vision_provider: VisionProvider, llm_provider: LLMProvider) -> None:
        self._vision = vision_provider
        self._llm = llm_provider

    def run(self, record: ProductRecord) -> PipelineResponse:
        image_reference = (
            (str(record.image_local_path) if record.image_local_path else None)
            or (str(record.image_url) if record.image_url else None)
            or record.image_path
        )
        if image_reference is None:
            raise ValueError(f"Record {record.product_id} is missing an image reference.")
        vision_hint = self._vision.describe(image_reference)
        llm_attributes: CoreAttributes = self._llm.classify(record, vision_hint)
        dimensions_attr = self._build_dimensions_attribute(record)
        attributes = CatalogAttributes(
            category=llm_attributes.category,
            room_type=llm_attributes.room_type,
            style=llm_attributes.style,
            material=llm_attributes.material,
            dimensions=dimensions_attr,
        )
        return PipelineResponse(
            product_id=record.product_id,
            generated_at=datetime.now(UTC),
            attributes=attributes,
        )

    def _build_dimensions_attribute(self, record: ProductRecord) -> AttributeResult:
        prediction = extract_dimensions_prediction(record.title, record.description)
        if isinstance(prediction.value, ExtractedDimensions):
            formatted = _format_dimensions(prediction.value)
            rationale = prediction.evidence[0] if prediction.evidence else "Parsed dimension rule." 
            return AttributeResult(
                value=formatted,
                confidence=prediction.confidence,
                rationale=rationale,
            )
        message = "No recognizable dimension pattern detected."
        if not (record.description or record.title):
            message = "No text provided for dimension parsing."
        return AttributeResult(value=None, confidence=0.2, rationale=message)


def build_default_pipeline() -> CatalogPipeline:
    """Return a pipeline wired with deterministic local providers."""

    return CatalogPipeline(vision_provider=MockVisionProvider(), llm_provider=MockLLMProvider())


def _format_dimensions(dimensions: ExtractedDimensions) -> str:
    parts = []
    for value in [dimensions.width, dimensions.depth, dimensions.height]:
        if value is not None:
            parts.append(_format_number(value))
    joined = " x ".join(parts)
    unit = dimensions.unit or ""
    unit_suffix = f" {unit}" if unit else ""
    return f"{joined}{unit_suffix}".strip()


def _format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")
