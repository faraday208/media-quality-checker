"""Scanner: collect_images, find_quality_issues, composite reasons."""
from pathlib import Path

import pytest

from quality_core import (
    ALL_CHECKS,
    DEFAULT_IMAGE_EXTS,
    collect_images,
    find_quality_issues,
)
from quality_core.scanner import _resolve_checks


# ---------- collect_images ----------

def test_collect_top_level(mixed_dataset: Path):
    files = collect_images(mixed_dataset, recursive=False)
    names = [p.name for p in files]
    assert "normal.jpg" in names
    assert "normal2.jpg" not in names  # alt klasör


def test_collect_recursive(mixed_dataset: Path):
    files = collect_images(mixed_dataset, recursive=True)
    names = [p.name for p in files]
    assert "normal2.jpg" in names
    assert "blurry2.jpg" in names


def test_collect_invalid_dir(tmp_path: Path):
    assert collect_images(tmp_path / "nope") == []


def test_collect_filters_by_ext(tmp_path: Path):
    (tmp_path / "a.jpg").write_bytes(b"")
    (tmp_path / "b.txt").write_bytes(b"hi")
    out = collect_images(tmp_path, allowed_exts={".jpg"})
    assert [p.name for p in out] == ["a.jpg"]


def test_collect_skips_rejected_and_report_dirs(tmp_path):
    """Recursive scan _rejected/report klasörlerini atlar."""
    (tmp_path / "keep.jpg").write_bytes(b"x")
    (tmp_path / "_rejected" / "03-quality").mkdir(parents=True)
    (tmp_path / "_rejected" / "03-quality" / "elenen.jpg").write_bytes(b"x")
    (tmp_path / "report").mkdir()
    (tmp_path / "report" / "rapor.jpg").write_bytes(b"x")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "deep.jpg").write_bytes(b"x")
    names = [p.name for p in collect_images(tmp_path, recursive=True)]
    assert "keep.jpg" in names
    assert "deep.jpg" in names
    assert "elenen.jpg" not in names
    assert "rapor.jpg" not in names


# ---------- _resolve_checks ----------

def test_resolve_checks_all_keyword():
    assert _resolve_checks(["all"]) == list(ALL_CHECKS)


def test_resolve_checks_partial():
    assert _resolve_checks(["blur", "bpp"]) == ["blur", "bpp"]


def test_resolve_checks_dedup():
    assert _resolve_checks(["blur", "blur", "bpp"]) == ["blur", "bpp"]


def test_resolve_checks_empty_defaults_all():
    assert _resolve_checks([]) == list(ALL_CHECKS)


# ---------- find_quality_issues ----------

def test_find_quality_returns_scan_result(mixed_dataset: Path, quality_config: dict):
    sr = find_quality_issues(mixed_dataset, config=quality_config, recursive=True)
    # 7 dosya: 5 top-level + 2 sub
    assert sr.total_scanned == 7
    assert sr.has_invalid


def test_find_quality_blur_detection(blurry_image: Path, quality_config: dict):
    sr = find_quality_issues(
        blurry_image.parent, config=quality_config,
        checks=["blur"], recursive=False,
    )
    # blur'lu dosya invalid olmalı
    invalid = [r for r in sr.results if not r["valid"]]
    assert len(invalid) == 1
    assert "blurry" in invalid[0]["reason"]


def test_find_quality_brightness_detection(dark_image: Path, bright_image: Path,
                                            quality_config: dict):
    sr = find_quality_issues(
        dark_image.parent, config=quality_config,
        checks=["brightness"], recursive=False,
    )
    # 2 invalid (dark + bright)
    invalid = [r for r in sr.results if not r["valid"]]
    assert len(invalid) == 2


def test_find_quality_contrast_detection(low_contrast_image: Path, quality_config: dict):
    sr = find_quality_issues(
        low_contrast_image.parent, config=quality_config,
        checks=["contrast"], recursive=False,
    )
    invalid = [r for r in sr.results if not r["valid"]]
    assert len(invalid) >= 1
    # reason'da contrast geçmeli
    assert any("contrast" in r["reason"] for r in invalid)


def test_find_quality_bpp_detection(tmp_path: Path, quality_config: dict):
    """Aşırı sıkıştırılmış görsel — BPP < 0.1 olmalı."""
    import numpy as np
    from PIL import Image
    # Düz renkli büyük görsel + low quality → düşük BPP
    arr = np.full((1024, 1024, 3), 128, dtype=np.uint8)
    Image.fromarray(arr).save(tmp_path / "lowbpp.jpg", "JPEG", quality=10)

    sr = find_quality_issues(
        tmp_path, config=quality_config,
        checks=["bpp"], recursive=False,
    )
    # BPP < 0.1 (düz renk q10 → çok sıkışır)
    invalid = [r for r in sr.results if not r["valid"]]
    assert len(invalid) >= 1


def test_find_quality_composite_reason(mixed_dataset: Path, quality_config: dict):
    """Birden fazla check fail ederse reason composite (virgülle) olur."""
    sr = find_quality_issues(mixed_dataset, config=quality_config, recursive=True)
    # dark image: brightness + contrast ikisi de fail eder
    dark_results = [r for r in sr.results if "dark.jpg" in r["filename"]]
    assert dark_results
    dark_reason = dark_results[0].get("reason", "")
    # En az iki invalid sebebi olmalı (brightness ve contrast)
    assert "," in dark_reason


def test_find_quality_normal_passes_all_checks(normal_image: Path, quality_config: dict):
    sr = find_quality_issues(
        normal_image.parent, config=quality_config, recursive=False,
    )
    valid = [r for r in sr.results if r["valid"]]
    assert len(valid) == 1


def test_find_quality_path_field_absolute(mixed_dataset: Path, quality_config: dict):
    """v1.0: result.path absolute (apply_action için kritik)."""
    sr = find_quality_issues(mixed_dataset, config=quality_config, recursive=True)
    for r in sr.results:
        assert Path(r["path"]).is_absolute()


def test_find_quality_only_enabled_checks(blurry_image: Path, quality_config: dict):
    """checks=['blur'] verilince sadece blur metric'i set olur, diğerleri None."""
    sr = find_quality_issues(
        blurry_image.parent, config=quality_config,
        checks=["blur"], recursive=False,
    )
    r = sr.results[0]
    assert r["blur_score"] is not None
    assert r["brightness_score"] is None
    assert r["contrast_score"] is None
    assert r["bpp_score"] is None


def test_find_quality_empty_dir(tmp_path: Path, quality_config: dict):
    sr = find_quality_issues(tmp_path, config=quality_config, recursive=True)
    assert sr.total_scanned == 0
    assert sr.results == []


def test_find_quality_progress_callback(mixed_dataset: Path, quality_config: dict):
    calls = []
    def cb(current, total, msg):
        calls.append((current, total, msg))
    find_quality_issues(
        mixed_dataset, config=quality_config, recursive=True, progress_cb=cb,
    )
    assert len(calls) >= 1


def test_default_image_exts():
    assert ".jpg" in DEFAULT_IMAGE_EXTS
    assert ".png" in DEFAULT_IMAGE_EXTS
    assert ".webp" in DEFAULT_IMAGE_EXTS
