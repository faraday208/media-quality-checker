"""Test fixture'ları — media-quality-checker."""
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageFilter

# Repo kökünü path'e ekle
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


DEFAULT_CONFIG = {
    "quality": {
        "blur_threshold": 100,
        "brightness": {"min": 30, "max": 225},
        "contrast_threshold": 15,
        "bpp": {"min": 0.1},
    },
}


def _save_random(path: Path, size=(256, 256)) -> None:
    """Yüksek frekanslı (sharp) görsel — random noise."""
    arr = np.random.randint(0, 256, (*size[::-1], 3), dtype=np.uint8)
    Image.fromarray(arr).save(path, "JPEG", quality=90)


def _save_blurry(path: Path, size=(256, 256)) -> None:
    """Random görsel + heavy gaussian blur → düşük blur_score."""
    arr = np.random.randint(0, 256, (*size[::-1], 3), dtype=np.uint8)
    img = Image.fromarray(arr).filter(ImageFilter.GaussianBlur(radius=10))
    img.save(path, "JPEG", quality=90)


def _save_solid(path: Path, color: tuple[int, int, int], size=(256, 256)) -> None:
    """Tek renk — düşük contrast (stddev=0)."""
    Image.new("RGB", size, color).save(path, "JPEG", quality=90)


@pytest.fixture
def quality_config() -> dict:
    import copy
    return copy.deepcopy(DEFAULT_CONFIG)


@pytest.fixture
def sharp_image(tmp_path: Path) -> Path:
    p = tmp_path / "sharp.jpg"
    _save_random(p)
    return p


@pytest.fixture
def blurry_image(tmp_path: Path) -> Path:
    p = tmp_path / "blurry.jpg"
    _save_blurry(p)
    return p


@pytest.fixture
def dark_image(tmp_path: Path) -> Path:
    p = tmp_path / "dark.jpg"
    _save_solid(p, (10, 10, 10))
    return p


@pytest.fixture
def bright_image(tmp_path: Path) -> Path:
    p = tmp_path / "bright.jpg"
    _save_solid(p, (245, 245, 245))
    return p


@pytest.fixture
def low_contrast_image(tmp_path: Path) -> Path:
    p = tmp_path / "low_contrast.jpg"
    _save_solid(p, (128, 128, 128))
    return p


@pytest.fixture
def normal_image(tmp_path: Path) -> Path:
    """Random — sharp + medium brightness + good contrast + reasonable BPP."""
    p = tmp_path / "normal.jpg"
    _save_random(p, size=(512, 512))
    return p


@pytest.fixture
def mixed_dataset(tmp_path: Path) -> Path:
    """Karışık quality dataset — composite scanner için.

    Yapı:
        tmp_path/
            normal.jpg          # tüm check'ler ✓
            sharp.jpg           # tüm check'ler ✓
            blurry.jpg          # blur INVALID
            dark.jpg            # brightness + contrast INVALID
            bright.jpg          # brightness + contrast INVALID
            sub/
                normal2.jpg     # tüm check'ler ✓
                blurry2.jpg     # blur INVALID
    """
    _save_random(tmp_path / "normal.jpg", (512, 512))
    _save_random(tmp_path / "sharp.jpg", (512, 512))
    _save_blurry(tmp_path / "blurry.jpg", (512, 512))
    _save_solid(tmp_path / "dark.jpg", (10, 10, 10), (512, 512))
    _save_solid(tmp_path / "bright.jpg", (245, 245, 245), (512, 512))
    sub = tmp_path / "sub"
    sub.mkdir()
    _save_random(sub / "normal2.jpg", (512, 512))
    _save_blurry(sub / "blurry2.jpg", (512, 512))
    return tmp_path
