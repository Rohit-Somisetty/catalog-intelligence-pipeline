from typing import cast

from pydantic import HttpUrl

from catalog_intelligence_pipeline.enrich import enrich_records
from catalog_intelligence_pipeline.schemas import IngestedProductRecord


def test_enrich_records_produces_predictions(sample_image_path) -> None:
    record = IngestedProductRecord(
        product_id="enrich-001",
        title="Modern Leather Sofa",
        description="A sleek living room sofa measuring 84 x 36 x 32 in.",
        image_url=cast(HttpUrl, "https://example.com/sofa.jpg"),
        image_path=str(sample_image_path),
        image_local_path=str(sample_image_path),
    )

    enriched = enrich_records([record])
    assert len(enriched) == 1

    predictions = enriched[0].predictions
    assert set(predictions.keys()) == {"category", "room_type", "style", "material", "dimensions"}
    assert predictions["category"].value in {"Sofa", "Sectional"}
    assert predictions["dimensions"].value is not None
    assert predictions["dimensions"].extracted_by == "rules"
