from catalog_intelligence_pipeline.fusion import fuse_predictions
from catalog_intelligence_pipeline.schemas import AttributePrediction, VisionQualityFlags


def _attr(value: str, confidence: float, source: str, evidence: list[str] | None = None) -> AttributePrediction:
    return AttributePrediction(value=value, confidence=confidence, extracted_by=source, evidence=evidence or [])


def test_fusion_agreement_boosts_confidence() -> None:
    text = {"category": _attr("Sofa", 0.8, "text", ["text snippet"])}
    vision = {"category": _attr("Sofa", 0.7, "vision", ["vision label"])}

    fused, log = fuse_predictions(text, vision, VisionQualityFlags())

    assert fused["category"].value == "Sofa"
    assert fused["category"].confidence > 0.8
    assert log["category"].chosen_source == "merged"


def test_fusion_prefers_higher_confidence_source() -> None:
    text = {"category": _attr("Chair", 0.5, "text")}
    vision = {"category": _attr("Sofa", 0.8, "vision")}

    fused, log = fuse_predictions(text, vision, VisionQualityFlags())

    assert fused["category"].value == "Sofa"
    assert log["category"].chosen_source == "vision"


def test_fusion_defaults_to_text_on_small_gap() -> None:
    text = {"category": _attr("Bench", 0.6, "text")}
    vision = {"category": _attr("Sofa", 0.55, "vision")}

    fused, log = fuse_predictions(text, vision, VisionQualityFlags())

    assert fused["category"].value == "Bench"
    assert fused["category"].confidence == 0.5
    assert "Sofa" in "".join(log["category"].conflicts)


def test_fusion_handles_unknowns() -> None:
    text = {"category": _attr("unknown", 0.35, "text")}
    vision = {"category": _attr("Sofa", 0.7, "vision")}

    fused, log = fuse_predictions(text, vision, VisionQualityFlags())

    assert fused["category"].value == "Sofa"
    assert log["category"].chosen_source == "vision"


def test_quality_flags_reduce_vision_confidence() -> None:
    text = {"category": _attr("Sofa", 0.8, "text")}
    vision = {"category": _attr("Sofa", 0.8, "vision")}

    fused, _ = fuse_predictions(text, vision, VisionQualityFlags(blurry=True))

    assert fused["category"].confidence < 0.9
