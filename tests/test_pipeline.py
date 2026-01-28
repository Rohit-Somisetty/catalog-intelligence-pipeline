from typing import cast

from pydantic import HttpUrl

from catalog_intelligence_pipeline.pipeline import build_default_pipeline
from catalog_intelligence_pipeline.schemas import ProductRecord


def test_pipeline_generates_expected_attributes(sample_image_path) -> None:
    pipeline = build_default_pipeline()
    record = ProductRecord(
        product_id="test-001",
        image_url=cast(HttpUrl, "https://example.com/assets/dining-table.png"),
        image_path=str(sample_image_path),
        image_local_path=str(sample_image_path),
        title="Modern Walnut Dining Table",
        description="Seats six people comfortably. Dimensions: 72 in x 38 in with tapered legs.",
    )

    result = pipeline.run(record)

    assert result.product_id == record.product_id
    assert result.attributes.category.value == "Table"
    assert result.attributes.room_type.value == "Dining Room"
    assert result.attributes.dimensions.value == "72 x 38 in"
    assert result.attributes.dimensions.confidence > 0.5
