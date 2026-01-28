from catalog_intelligence_pipeline.extractors.vision_attributes import map_vision_predictions
from catalog_intelligence_pipeline.providers.vision import MockVisionProvider
from catalog_intelligence_pipeline.schemas import VisionLabel, VisionPrediction, VisionQualityFlags


def test_vision_predict_is_deterministic(sample_image_path) -> None:
    provider = MockVisionProvider()
    prediction_a = provider.predict(str(sample_image_path))
    prediction_b = provider.predict(str(sample_image_path))

    assert prediction_a == prediction_b
    assert len(prediction_a.labels) == 3
    assert prediction_a.trace_id


def test_map_vision_predictions_generates_category() -> None:
    prediction = VisionPrediction(
        labels=[VisionLabel(name="sofa", confidence=0.9)],
        quality_flags=VisionQualityFlags(),
        trace_id="trace123",
    )

    attrs = map_vision_predictions(prediction)

    assert attrs["category"].value == "Sofa"
    assert attrs["room_type"].value == "Living Room"
    assert attrs["style"].value == "unknown"
