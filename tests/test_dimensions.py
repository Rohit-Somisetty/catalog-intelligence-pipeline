from catalog_intelligence_pipeline.extractors.dimensions import extract_dimensions_prediction
from catalog_intelligence_pipeline.schemas import AttributePrediction, ExtractedDimensions


def _require_dimensions_value(prediction: AttributePrediction) -> ExtractedDimensions:
    value = prediction.value
    assert value is not None
    assert isinstance(value, ExtractedDimensions)
    return value


def test_extract_dimensions_three_axis_pattern() -> None:
    text = "Overall size: 80 x 60 x 35 in for spacious seating."
    prediction = extract_dimensions_prediction("Walnut Sofa", text)
    dims = _require_dimensions_value(prediction)
    assert dims.width == 80
    assert dims.depth == 60
    assert dims.height == 35
    assert dims.unit == "in"
    assert prediction.evidence


def test_extract_dimensions_metric_values() -> None:
    text = "Dimensions: 200x150x90 cm frame."
    prediction = extract_dimensions_prediction("Platform Bed", text)
    dims = _require_dimensions_value(prediction)
    assert dims.unit == "cm"
    assert dims.height == 90


def test_extract_dimensions_with_quotes_and_labels() -> None:
    text = "Measures 72\"W x 38\"D x 30\"H overall."
    prediction = extract_dimensions_prediction("Dining Table", text)
    dims = _require_dimensions_value(prediction)
    assert dims.unit == "in"
    assert dims.width == 72


def test_extract_dimensions_label_pattern() -> None:
    text = "Specs: W: 55 cm, D: 30 cm, H: 18 cm base."
    prediction = extract_dimensions_prediction("Console Table", text)
    dims = _require_dimensions_value(prediction)
    assert dims.width == 55
    assert dims.height == 18


def test_extract_dimensions_two_axis_variant() -> None:
    text = "Footprint: 42x18 inches to fit hallways."
    prediction = extract_dimensions_prediction("Entry Bench", text)
    dims = _require_dimensions_value(prediction)
    assert dims.depth == 18


def test_extract_dimensions_handles_letter_labels() -> None:
    text = "Compact form: Width 30 in x Depth 20 in"
    prediction = extract_dimensions_prediction("Side Table", text)
    dims = _require_dimensions_value(prediction)
    assert dims.width == 30
    assert dims.depth == 20
