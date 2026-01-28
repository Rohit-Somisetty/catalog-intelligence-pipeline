"""Map vision predictions to catalog attribute predictions."""

from __future__ import annotations

from ..schemas import AttributePrediction, VisionPrediction

_EXTRACTED_BY = "vision_stub"
_UNKNOWN = AttributePrediction(value="unknown", confidence=0.35, extracted_by=_EXTRACTED_BY, evidence=[])

_CATEGORY_MAP = {
	"sofa": "Sofa",
	"sectional": "Sectional",
	"bed": "Bed",
	"table": "Table",
	"chair": "Chair",
	"lamp": "Lighting",
	"dresser": "Dresser",
	"rug": "Rug",
	"desk": "Desk",
	"bench": "Bench",
}

_ROOM_MAP = {
	"sofa": "Living Room",
	"sectional": "Living Room",
	"bed": "Bedroom",
	"table": "Dining Room",
	"lamp": "Living Room",
	"rug": "Living Room",
	"desk": "Home Office",
	"bench": "Entryway",
}


def map_vision_predictions(prediction: VisionPrediction) -> dict[str, AttributePrediction]:
	labels = prediction.labels
	if not labels:
		return {
			"category": _UNKNOWN,
			"room_type": _UNKNOWN,
			"style": _UNKNOWN,
			"material": _UNKNOWN,
		}

	top_label = labels[0]
	category = _build_prediction(top_label.name, top_label.confidence, _CATEGORY_MAP)
	room = _build_prediction(top_label.name, top_label.confidence, _ROOM_MAP)

	return {
		"category": category,
		"room_type": room,
		"style": _UNKNOWN,
		"material": _UNKNOWN,
	}


def _build_prediction(label: str, confidence: float, mapping: dict[str, str]) -> AttributePrediction:
	normalized = label.lower()
	if normalized in mapping:
		evidence = [f"vision label: {mapping[normalized]} ({label})"]
		return AttributePrediction(
			value=mapping[normalized],
			confidence=confidence,
			extracted_by=_EXTRACTED_BY,
			evidence=evidence,
		)
	return _UNKNOWN
