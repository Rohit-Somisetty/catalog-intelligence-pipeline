"""Rule-based dimension extraction utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..schemas import AttributePrediction, ExtractedDimensions

_UNIT_PATTERN = "cm|mm|m|in|inch|inches|ft|feet"
_AXIS_PATTERN = re.compile(
    rf"(?P<w>\d+(?:\.\d+)?)\s*(?P<unit_w>{_UNIT_PATTERN})?\s*(?:[\"”]?\s*(?:w|width))?\s*(?:x|×)\s*"
    rf"(?P<d>\d+(?:\.\d+)?)\s*(?P<unit_d>{_UNIT_PATTERN})?\s*(?:[\"”]?\s*(?:d|depth))?"
    rf"(?:\s*(?:x|×)\s*(?P<h>\d+(?:\.\d+)?)\s*(?P<unit_h>{_UNIT_PATTERN})?\s*(?:[\"”]?\s*(?:h|height))?)?"
    rf"\s*(?P<trailing_unit>{_UNIT_PATTERN})?",
    flags=re.IGNORECASE,
)
_LABEL_PATTERN = re.compile(
    rf"(?P<label>w|width|d|depth|h|height)\s*(?:[:=]\s*)?(?P<value>\d+(?:\.\d+)?)(?:\s*(?P<unit>{_UNIT_PATTERN}))?",
    flags=re.IGNORECASE,
)


@dataclass
class _Candidate:
    dimensions: ExtractedDimensions
    evidence: str
    score: int
    source_index: int
    position: int


def extract_dimensions_prediction(title: str, description: str | None) -> AttributePrediction:
    """Return an attribute prediction describing dimensions found in text."""

    sources = [text for text in [description, title] if text]
    if not sources:
        return AttributePrediction(value=None, confidence=0.2, extracted_by="rules", evidence=[])

    candidates: list[_Candidate] = []
    for idx, text in enumerate(sources):
        candidates.extend(_find_axis_candidates(text, idx))
        candidates.extend(_find_label_candidates(text, idx))

    if not candidates:
        return AttributePrediction(value=None, confidence=0.2, extracted_by="rules", evidence=[])

    best = max(candidates, key=lambda c: (c.score, -c.source_index, -c.position))
    dims = best.dimensions
    evidence = [best.evidence.strip()]
    dims_count = _dimension_count(dims)
    confidence = 0.95 if dims_count == 3 else 0.85 if dims_count == 2 else 0.75

    return AttributePrediction(value=dims, confidence=confidence, extracted_by="rules", evidence=evidence)


def _find_axis_candidates(text: str, source_index: int) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    for match in _AXIS_PATTERN.finditer(text):
        width = _parse_float(match.group("w"))
        depth = _parse_float(match.group("d"))
        height = _parse_float(match.group("h"))
        unit = _select_unit(match)
        if not width and not depth and not height:
            continue
        dims = ExtractedDimensions(width=width, depth=depth, height=height, unit=unit)
        evidence = match.group(0)
        score = _score_candidate(dims)
        candidates.append(
            _Candidate(
                dimensions=dims,
                evidence=evidence,
                score=score,
                source_index=source_index,
                position=match.start(),
            ),
        )
    return candidates


def _select_unit(match: re.Match[str]) -> str | None:
    for key in [
        "trailing_unit",
        "unit_w",
        "unit_d",
        "unit_h",
    ]:
        candidate = match.groupdict().get(key)
        if candidate:
            normalized = _normalize_unit(candidate)
            if normalized:
                return normalized
    return _infer_unit_from_match(match.group(0))


def _find_label_candidates(text: str, source_index: int) -> list[_Candidate]:
    matches = list(_LABEL_PATTERN.finditer(text))
    if not matches:
        return []

    candidates: list[_Candidate] = []
    current_dims = ExtractedDimensions()
    current_start: int | None = None
    last_end: int | None = None
    labels_seen: list[str] = []

    def _flush_candidate(end_index: int) -> None:
        nonlocal current_dims, current_start, last_end, labels_seen
        if _dimension_count(current_dims) >= 2 and current_start is not None:
            evidence = text[current_start:end_index]
            dims_copy = ExtractedDimensions(**current_dims.model_dump())
            candidates.append(
                _Candidate(
                    dimensions=dims_copy,
                    evidence=evidence,
                    score=_score_candidate(dims_copy),
                    source_index=source_index,
                    position=current_start,
                )
            )
        current_dims = ExtractedDimensions()
        current_start = None
        last_end = None
        labels_seen = []

    for match in matches:
        label = match.group("label").lower()[0]
        value = _parse_float(match.group("value"))
        unit = _normalize_unit(match.group("unit"))

        if label in labels_seen:
            _flush_candidate(match.start())

        current_start = match.start() if current_start is None else current_start
        last_end = match.end()
        labels_seen.append(label)
        _assign_dimension(current_dims, label, value, unit)

    if current_start is not None and last_end is not None:
        _flush_candidate(last_end)

    return candidates


def _assign_dimension(dims: ExtractedDimensions, label: str, value: float | None, unit: str | None) -> None:
    if value is None:
        return
    if label == "w" and dims.width is None:
        dims.width = value
    elif label == "d" and dims.depth is None:
        dims.depth = value
    elif label == "h" and dims.height is None:
        dims.height = value

    if not dims.unit and unit:
        dims.unit = unit


def _score_candidate(dims: ExtractedDimensions) -> int:
    dims_count = _dimension_count(dims)
    score = dims_count * 10
    if dims.unit:
        score += 1
    return score


def _dimension_count(dims: ExtractedDimensions) -> int:
    return sum(1 for value in [dims.width, dims.depth, dims.height] if value is not None)


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _normalize_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    unit = unit.lower()
    if unit in {"inch", "inches"}:
        return "in"
    if unit in {"feet", "foot"}:
        return "ft"
    return unit


def _infer_unit_from_match(text: str) -> str | None:
    if '"' in text or "”" in text:
        return "in"
    if "'" in text:
        return "ft"
    return None
