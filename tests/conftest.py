from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
_SAMPLE_IMAGE = FIXTURES_DIR / "sample_image.png"

if not _SAMPLE_IMAGE.exists():
    image = Image.new("RGB", (2, 2), color=(255, 255, 255))
    image.save(_SAMPLE_IMAGE)


@pytest.fixture()
def sample_image_path(tmp_path: Path) -> Path:
    target = tmp_path / "sample.png"
    target.write_bytes(_SAMPLE_IMAGE.read_bytes())
    return target


@pytest.fixture()
def sample_image_bytes() -> bytes:
    return _SAMPLE_IMAGE.read_bytes()
