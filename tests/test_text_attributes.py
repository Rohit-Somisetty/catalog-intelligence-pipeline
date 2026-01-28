from catalog_intelligence_pipeline.extractors.text_attributes import extract_text_attributes


def test_extract_text_attributes_category_and_style() -> None:
    predictions = extract_text_attributes(
        "Mid-Century Walnut Dining Table",
        "Perfect for dining room gatherings with solid walnut construction.",
    )

    category = predictions["category"]
    style = predictions["style"]
    material = predictions["material"]

    assert category.value in {"Table", "Dining Table"}
    assert style.value == "Mid-Century"
    assert material.value in {"Walnut", "Wood"}
    assert category.confidence >= 0.75
    assert style.confidence == 0.9
    assert material.evidence


def test_extract_text_attributes_room_and_fallback() -> None:
    predictions = extract_text_attributes("Outdoor Garden Bench", "Weather-resistant bench for patios.")

    room = predictions["room_type"]
    assert room.value == "Outdoor"
    assert room.confidence >= 0.75

    unknown_style = predictions["style"]
    assert unknown_style.value == "unknown"
    assert unknown_style.confidence == 0.4