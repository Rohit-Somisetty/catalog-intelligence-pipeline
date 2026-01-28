from catalog_intelligence_pipeline.enrich import enrich_records
from catalog_intelligence_pipeline.predict import predict_records
from catalog_intelligence_pipeline.schemas import IngestedProductRecord


def test_predict_records_produces_final_predictions(sample_image_path) -> None:
    record = IngestedProductRecord(
        product_id="predict-001",
        title="Contemporary Fabric Sofa",
        description="Soft fabric sofa perfect for living rooms. Measures 84 x 34 x 32 in.",
        image_url="https://example.com/sofa.jpg",
        image_path=str(sample_image_path),
        image_local_path=str(sample_image_path),
    )

    enriched = enrich_records([record])
    predictions = predict_records(enriched)

    assert len(predictions) == 1
    output = predictions[0]
    assert set(output.final_predictions.keys()) == {"category", "room_type", "style", "material"}
    assert "category" in output.decision_log
    assert output.final_predictions["category"].value
    assert output.decision_log["category"].chosen_source
