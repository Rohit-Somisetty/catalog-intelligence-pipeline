"""Pydantic data models shared across the pipeline, API, and CLI."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, model_validator


class RawProductRecord(BaseModel):
    """User-provided payload prior to ingestion."""

    product_id: str = Field(..., description="Primary identifier from the source catalog.")
    title: str = Field(..., description="Short marketing title.")
    description: str | None = Field(default=None, description="Long-form copy that may contain attributes.")
    image_url: HttpUrl | None = Field(default=None, description="Public URL of the hero image.")
    image_path: str | None = Field(default=None, description="Optional pointer to an existing local image file.")
    brand: str | None = Field(default=None, description="Optional brand metadata passed through downstream.")
    sku: str | None = Field(default=None, description="Optional SKU identifier.")
    price: float | None = Field(default=None, description="Optional numeric price for analytics.")
    currency: str | None = Field(default=None, description="ISO currency code for price, when provided.")

    @model_validator(mode="after")
    def _ensure_image_reference(self) -> RawProductRecord:
        if not (self.image_url or self.image_path):
            raise ValueError("Each record must include image_url or image_path.")
        return self


class ProductRecord(RawProductRecord):
    """Pipeline-ready payload with a resolved local image path."""

    image_local_path: str | None = Field(
        default=None,
        description="Resolved local filesystem path to the product image.",
    )

    @model_validator(mode="after")
    def _validate_image_sources(self) -> ProductRecord:
        if not (self.image_local_path or self.image_url or self.image_path):
            raise ValueError("At least one image reference (local path or URL) must be present.")
        return self


class IngestedProductRecord(ProductRecord):
    """Product payload after ingestion with a guaranteed local image path."""

    image_local_path: str = Field(..., description="Resolved local filesystem path to the product image.")


class AttributeResult(BaseModel):
    """Normalized attribute with value, confidence, and rationale snippet."""

    value: str | None = Field(default=None, description="Final extracted value, if detected.")
    confidence: float = Field(..., ge=0, le=1, description="Heuristic confidence score (0-1).")
    rationale: str = Field(..., description="Short note describing why the value was chosen.")


class CoreAttributes(BaseModel):
    """Attributes predicted by the language model provider."""

    category: AttributeResult
    room_type: AttributeResult
    style: AttributeResult
    material: AttributeResult


class CatalogAttributes(CoreAttributes):
    """Full attribute bundle including dimensions parsed from text."""

    dimensions: AttributeResult


class PipelineResponse(BaseModel):
    """Structured response emitted by the catalog pipeline."""

    product_id: str
    generated_at: datetime
    attributes: CatalogAttributes


class InferenceResponse(BaseModel):
    """API response body for batch predict endpoints."""

    results: list[PipelineResponse]


class InferenceRequest(BaseModel):
    """API request body for batch predict endpoints."""

    records: list[ProductRecord]

    @classmethod
    def from_iterable(cls, records: Iterable[ProductRecord]) -> InferenceRequest:
        return cls(records=list(records))


class IngestError(BaseModel):
    """Structured ingest error entry persisted to JSONL."""

    product_id: str
    error_type: str
    message: str


class APIError(BaseModel):
    """Standardized API error payload."""

    product_id: str | None = None
    error_type: str
    message: str
    stage: str
    details: dict[str, Any] | None = None


class IndexedAPIError(APIError):
    """API error that also captures the batch index for troubleshooting."""

    index: int


class ExtractedDimensions(BaseModel):
    """Normalized dimension payload detected from unstructured copy."""

    width: float | None = Field(default=None, description="Width component, if parsed.")
    depth: float | None = Field(default=None, description="Depth component, if parsed.")
    height: float | None = Field(default=None, description="Height component, if parsed.")
    unit: str | None = Field(default=None, description="Unit captured from the source text (e.g., in, cm).")


class AttributePrediction(BaseModel):
    """Generalized attribute payload with provenance metadata."""

    value: str | ExtractedDimensions | None = Field(
        default=None,
        description="Resolved value for the attribute; may contain structured dimensions.",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    extracted_by: str = Field(..., description="Identifier for the component that produced this value.")
    evidence: list[str] = Field(default_factory=list, description="Snippet(s) that justified the prediction.")


class EnrichedProductRecord(IngestedProductRecord):
    """Ingested record augmented with attribute predictions."""

    predictions: dict[str, AttributePrediction]


class VisionLabel(BaseModel):
    """Single label emitted by the vision provider."""

    name: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class VisionQualityFlags(BaseModel):
    """Quality indicators describing the source image."""

    blurry: bool = False
    low_res: bool = False
    dark: bool = False


class VisionPrediction(BaseModel):
    """Vision model output consumed by the fusion layer."""

    labels: list[VisionLabel]
    quality_flags: VisionQualityFlags
    trace_id: str


class DecisionLogEntry(BaseModel):
    """Explains how the final attribute value was chosen."""

    sources_considered: list[str]
    chosen_source: str
    reason: str
    conflicts: list[str] = Field(default_factory=list)


class PredictedProductRecord(EnrichedProductRecord):
    """Product record after text + vision fusion."""

    final_predictions: dict[str, AttributePrediction]
    decision_log: dict[str, DecisionLogEntry]


class PredictBatchResponse(BaseModel):
    """API response for fused prediction batches."""

    items: list[PredictedProductRecord]
    errors: list[IndexedAPIError]


class EnrichBatchResponse(BaseModel):
    """API response for enrichment batches."""

    items: list[EnrichedProductRecord]
    errors: list[IndexedAPIError]


class EnrichBatchRequest(BaseModel):
    """Batch request for enrichment."""

    items: list[ProductRecord]


class PredictBatchRequest(BaseModel):
    """Batch request for fused predictions."""

    items: list[EnrichedProductRecord | ProductRecord]
