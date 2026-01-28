"""Fusion logic that combines text and vision attribute predictions."""

from __future__ import annotations

from .schemas import AttributePrediction, DecisionLogEntry, ExtractedDimensions, VisionQualityFlags

_ATTR_KEYS = ["category", "room_type", "style", "material"]
_UNKNOWN_VALUE = "unknown"


def fuse_predictions(
	text_predictions: dict[str, AttributePrediction],
	vision_predictions: dict[str, AttributePrediction],
	quality_flags: VisionQualityFlags,
) -> tuple[dict[str, AttributePrediction], dict[str, DecisionLogEntry]]:
	fused: dict[str, AttributePrediction] = {}
	log: dict[str, DecisionLogEntry] = {}

	quality_penalty = 0.15 if (quality_flags.blurry or quality_flags.low_res or quality_flags.dark) else 0.0

	for key in _ATTR_KEYS:
		text_attr = text_predictions.get(key) or _unknown_prediction(source="text")
		vision_attr = vision_predictions.get(key) or _unknown_prediction(source="vision")

		adjusted_vision_conf = max(0.0, vision_attr.confidence - quality_penalty)
		vision_attr = AttributePrediction(
			value=vision_attr.value,
			confidence=adjusted_vision_conf,
			extracted_by=vision_attr.extracted_by,
			evidence=vision_attr.evidence,
		)

		fused_attr, entry = _fuse_attribute(key, text_attr, vision_attr)
		if quality_penalty > 0 and not entry.reason.endswith("vision confidence adjusted"):
			entry.reason += " (vision confidence adjusted)"
		fused[key] = fused_attr
		log[key] = entry

	return fused, log


def _fuse_attribute(
	key: str,
	text_attr: AttributePrediction,
	vision_attr: AttributePrediction,
) -> tuple[AttributePrediction, DecisionLogEntry]:
	sources = ["text", "vision"]
	text_value = _normalize_value(text_attr.value)
	vision_value = _normalize_value(vision_attr.value)
	text_display = _stringify_value(text_attr.value)
	vision_display = _stringify_value(vision_attr.value)

	if text_value and vision_value and text_value == vision_value:
		confidence = min(0.98, max(text_attr.confidence, vision_attr.confidence) + 0.05)
		evidence = _unique_list(text_attr.evidence + vision_attr.evidence)
		attr = AttributePrediction(
			value=text_attr.value,
			confidence=confidence,
			extracted_by="fusion",
			evidence=evidence,
		)
		log = DecisionLogEntry(
			sources_considered=sources,
			chosen_source="merged",
			reason="Text and vision agreed on the attribute value.",
		)
		return attr, log

	if text_value == _UNKNOWN_VALUE and vision_value != _UNKNOWN_VALUE:
		attr = vision_attr
		log = DecisionLogEntry(
			sources_considered=sources,
			chosen_source="vision",
			reason="Vision provided a value while text was unknown.",
			conflicts=[f"text={text_display}"] if text_display else [],
		)
		return attr, log

	if vision_value == _UNKNOWN_VALUE and text_value != _UNKNOWN_VALUE:
		attr = text_attr
		log = DecisionLogEntry(
			sources_considered=sources,
			chosen_source="text",
			reason="Text provided a value while vision was unknown.",
			conflicts=[f"vision={vision_display}"] if vision_display else [],
		)
		return attr, log

	confidence_delta = text_attr.confidence - vision_attr.confidence
	if abs(confidence_delta) >= 0.20:
		if confidence_delta > 0:
			attr = text_attr
			chosen = "text"
		else:
			attr = vision_attr
			chosen = "vision"
		log = DecisionLogEntry(
			sources_considered=sources,
			chosen_source=chosen,
			reason="One modality had substantially higher confidence.",
			conflicts=[f"text={text_display}", f"vision={vision_display}"],
		)
		attr = AttributePrediction(
			value=attr.value,
			confidence=attr.confidence,
			extracted_by="fusion",
			evidence=attr.evidence,
		)
		return attr, log

	reduced_confidence = max(0.0, text_attr.confidence - 0.10)
	attr = AttributePrediction(
		value=text_attr.value,
		confidence=reduced_confidence,
		extracted_by="fusion",
		evidence=text_attr.evidence,
	)
	log = DecisionLogEntry(
		sources_considered=sources,
		chosen_source="text",
		reason="Small confidence gap; defaulting to text.",
		conflicts=[f"text={text_display}", f"vision={vision_display}"],
	)
	return attr, log


def _unknown_prediction(source: str) -> AttributePrediction:
	return AttributePrediction(
		value=_UNKNOWN_VALUE,
		confidence=0.35,
		extracted_by=source,
		evidence=[],
	)


def _normalize_value(value: str | ExtractedDimensions | dict | None) -> str | None:
	if value is None:
		return None
	if isinstance(value, str):
		return value.lower().strip()
	return None


def _stringify_value(value: str | ExtractedDimensions | dict | None) -> str:
	if value is None:
		return ""
	if isinstance(value, str):
		return value
	if isinstance(value, ExtractedDimensions):
		return value.model_dump_json()
	return str(value)


def _unique_list(items: list[str]) -> list[str]:
	seen = set()
	unique: list[str] = []
	for item in items:
		if item not in seen:
			seen.add(item)
			unique.append(item)
	return unique