"""Helpers for generating deterministic demo payloads."""

from __future__ import annotations

from pathlib import Path
from random import Random

from PIL import Image, ImageDraw

from .schemas import RawProductRecord

_COLORS = [
    (234, 67, 53),
    (52, 168, 83),
    (66, 133, 244),
    (251, 188, 5),
    (124, 77, 255),
]
_ITEMS = ["Sofa", "Dining Chair", "Coffee Table", "Desk Lamp", "Bed", "Bookshelf"]
_STYLES = ["Modern", "Mid-Century", "Minimalist", "Scandi", "Industrial"]
_MATERIALS = ["Walnut", "Oak", "Velvet", "Leather", "Brass"]


def generate_synthetic_records(
    count: int,
    image_dir: Path,
    *,
    seed: int = 42,
) -> list[RawProductRecord]:
    """Return deterministic RawProductRecord objects for demos/benchmarks."""

    rng = Random(seed)
    fixtures = _ensure_fixture_images(image_dir, max(3, min(10, count)))
    records: list[RawProductRecord] = []

    for idx in range(count):
        product_id = f"demo-{idx:04d}"
        style = _pick(rng, _STYLES)
        item = _pick(rng, _ITEMS)
        material = _pick(rng, _MATERIALS)
        color = _pick(rng, ["Walnut", "Slate", "Ivory", "Teal", "Charcoal"])
        title = f"{style} {material} {item}"
        desc_base = f"{style} {item.lower()} crafted with {material.lower()} accents and {color.lower()} finish."
        description = desc_base if rng.random() > 0.2 else None
        image_path = fixtures[idx % len(fixtures)]
        include_remote = idx % 2 == 0
        image_url = f"https://demo.catalog/{product_id}.jpg" if include_remote else None

        record = RawProductRecord(
            product_id=product_id,
            title=title,
            description=description,
            image_url=image_url,
            image_path=str(image_path),
            brand=_pick(rng, ["Acme Living", "Studio Loft", "UrbanCraft"]),
            sku=f"SKU-{idx:05d}",
            price=round(rng.uniform(49, 999), 2),
            currency="USD",
        )
        records.append(record)

    return records


def _ensure_fixture_images(image_dir: Path, count: int) -> list[Path]:
    image_dir.mkdir(parents=True, exist_ok=True)
    fixtures: list[Path] = []

    for idx in range(count):
        target = image_dir / f"fixture_{idx}.png"
        if not target.exists():
            color = _COLORS[idx % len(_COLORS)]
            image = Image.new("RGB", (96, 96), color=color)
            draw = ImageDraw.Draw(image)
            draw.text((28, 36), str(idx), fill=(255, 255, 255))
            image.save(target)
        fixtures.append(target)

    return fixtures


def _pick(rng: Random, items: list[str]) -> str:
    return rng.choice(items)
