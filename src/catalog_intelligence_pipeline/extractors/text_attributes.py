"""Deterministic text-based attribute extraction heuristics."""

from __future__ import annotations

import re
from collections.abc import Iterable

from ..schemas import AttributePrediction

_EXTRACTED_BY = "llm_stub"
_DEFAULT_VALUE = "unknown"
_SNIPPET_RADIUS = 35

CATEGORY_PHRASES: dict[str, str] = {
    "sectional sofa": "Sectional",
    "dining table": "Table",
    "coffee table": "Coffee Table",
    "accent chair": "Chair",
    "bar stool": "Stool",
}
CATEGORY_KEYWORDS: dict[str, str] = {
    "sofa": "Sofa",
    "couch": "Sofa",
    "sectional": "Sectional",
    "loveseat": "Sofa",
    "chair": "Chair",
    "stool": "Stool",
    "bench": "Bench",
    "table": "Table",
    "desk": "Desk",
    "lamp": "Lighting",
    "bed": "Bed",
    "dresser": "Dresser",
}

ROOM_PHRASES: dict[str, str] = {
    "living room": "Living Room",
    "dining room": "Dining Room",
    "home office": "Home Office",
    "entryway": "Entryway",
    "kids room": "Kids Room",
}
ROOM_KEYWORDS: dict[str, str] = {
    "bedroom": "Bedroom",
    "dining": "Dining Room",
    "office": "Home Office",
    "outdoor": "Outdoor",
    "patio": "Outdoor",
    "hallway": "Entryway",
    "nursery": "Kids Room",
}

STYLE_PHRASES: dict[str, str] = {
    "mid-century modern": "Mid-Century",
    "mid-century": "Mid-Century",
    "art deco": "Art Deco",
    "farmhouse chic": "Farmhouse",
}
STYLE_KEYWORDS: dict[str, str] = {
    "mid-century": "Mid-Century",
    "midcentury": "Mid-Century",
    "modern": "Modern",
    "rustic": "Rustic",
    "industrial": "Industrial",
    "boho": "Bohemian",
    "bohemian": "Bohemian",
    "scandi": "Scandinavian",
    "scandinavian": "Scandinavian",
    "farmhouse": "Farmhouse",
    "traditional": "Traditional",
    "minimalist": "Minimalist",
    "coastal": "Coastal",
}

MATERIAL_PHRASES: dict[str, str] = {
    "solid wood": "Wood",
    "top-grain leather": "Leather",
}
MATERIAL_KEYWORDS: dict[str, str] = {
    "walnut": "Walnut",
    "oak": "Oak",
    "pine": "Pine",
    "leather": "Leather",
    "linen": "Linen",
    "velvet": "Velvet",
    "boucle": "Boucle",
    "metal": "Metal",
    "steel": "Metal",
    "iron": "Metal",
    "aluminum": "Metal",
    "glass": "Glass",
    "rattan": "Rattan",
    "bamboo": "Bamboo",
    "marble": "Marble",
    "stone": "Stone",
}


def extract_text_attributes(title: str, description: str | None) -> dict[str, AttributePrediction]:
    """Return attribute predictions derived from catalog text fields."""

    sources = [value for value in [title, description] if value]
    lowered_sources = [value.lower() for value in sources]
    combined = " \n ".join(lowered_sources)

    category = _predict_attribute(
        combined,
        sources,
        CATEGORY_PHRASES,
        CATEGORY_KEYWORDS,
    )
    room = _predict_attribute(
        combined,
        sources,
        ROOM_PHRASES,
        ROOM_KEYWORDS,
    )
    style = _predict_attribute(
        combined,
        sources,
        STYLE_PHRASES,
        STYLE_KEYWORDS,
    )
    material = _predict_attribute(
        combined,
        sources,
        MATERIAL_PHRASES,
        MATERIAL_KEYWORDS,
    )

    return {
        "category": category,
        "room_type": room,
        "style": style,
        "material": material,
    }


def _predict_attribute(
    combined_text: str,
    sources: list[str],
    phrase_mapping: dict[str, str],
    keyword_mapping: dict[str, str],
) -> AttributePrediction:
    for phrase, label in phrase_mapping.items():
        if phrase in combined_text:
            snippet = _extract_snippet(sources, phrase)
            return AttributePrediction(
                value=label,
                confidence=0.9,
                extracted_by=_EXTRACTED_BY,
                evidence=[snippet] if snippet else [phrase],
            )

    for keyword, label in keyword_mapping.items():
        boundary_pattern = re.compile(rf"\b{re.escape(keyword)}\b")
        if boundary_pattern.search(combined_text):
            snippet = _extract_snippet(sources, keyword)
            return AttributePrediction(
                value=label,
                confidence=0.75,
                extracted_by=_EXTRACTED_BY,
                evidence=[snippet] if snippet else [keyword],
            )

    return AttributePrediction(
        value=_DEFAULT_VALUE,
        confidence=0.4,
        extracted_by=_EXTRACTED_BY,
        evidence=[],
    )


def _extract_snippet(sources: Iterable[str], needle: str) -> str:
    for source in sources:
        lowered = source.lower()
        idx = lowered.find(needle)
        if idx == -1:
            continue
        start = max(0, idx - _SNIPPET_RADIUS)
        end = min(len(source), idx + len(needle) + _SNIPPET_RADIUS)
        snippet = source[start:end].strip()
        if snippet:
            return snippet
    return needle
