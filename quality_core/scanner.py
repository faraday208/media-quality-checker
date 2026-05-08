"""
Quality Scanner — collect_images + composite quality check.

Public API:
- collect_images(directory, recursive, allowed_exts) → list[Path]
- find_quality_issues(directory, *, recursive, checks, config, ...) → ScanResult
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from .checkers import (
    BlurChecker,
    BPPChecker,
    BrightnessChecker,
    ContrastChecker,
)

DEFAULT_IMAGE_EXTS: frozenset[str] = frozenset({
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"
})

ALL_CHECKS = ("blur", "brightness", "contrast", "bpp")

ProgressCallback = Callable[[int, int, str], None]


@dataclass
class QualityResult:
    """Bir dosyanın 4 quality check'i için composite sonuç.

    valid: tüm enabled check'ler geçti mi
    reason: invalid'se virgülle ayrı kompozit (örn. 'blurry,dark')
    Per-metric alanlar: check çalışmadıysa None
    """
    valid: bool
    reason: str | None
    filename: str
    path: str          # absolute — apply_action'ın doğru dosyayı çözmesi için
    file_size_kb: float = 0.0
    width: int = 0
    height: int = 0

    # Blur
    blur_score: float | None = None
    is_blurry: bool | None = None
    # Brightness
    brightness_score: float | None = None
    brightness_status: str | None = None  # 'ok' | 'too_dark' | 'too_bright'
    # Contrast
    contrast_score: float | None = None
    is_low_contrast: bool | None = None
    # BPP
    bpp_score: float | None = None
    is_over_compressed: bool | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScanResult:
    """find_quality_issues çıktısı."""
    source_root: str
    total_scanned: int
    valid_count: int
    invalid_count: int
    enabled_checks: list[str]
    reasons: dict[str, int] = field(default_factory=dict)  # 'blurry': 5, 'dark': 3
    results: list[dict] = field(default_factory=list)      # QualityResult.to_dict()

    @property
    def has_invalid(self) -> bool:
        return self.invalid_count > 0


def collect_images(
    directory: Path | str,
    *,
    recursive: bool = True,
    allowed_exts: Iterable[str] = DEFAULT_IMAGE_EXTS,
) -> list[Path]:
    """Görsel dosyaları topla (validator/deduplicator ile aynı pattern)."""
    root = Path(directory)
    if not root.is_dir():
        return []
    exts = {e.lower() for e in allowed_exts}
    out: list[Path] = []
    if recursive:
        for dirpath, _dn, filenames in os.walk(root, followlinks=False):
            for fn in filenames:
                p = Path(dirpath) / fn
                if p.suffix.lower() in exts:
                    out.append(p)
    else:
        for entry in root.iterdir():
            if entry.is_file() and entry.suffix.lower() in exts:
                out.append(entry)
    out.sort()
    return out


def _resolve_checks(checks: Iterable[str]) -> list[str]:
    """'all' veya boş → tüm check'ler. Kümeyi sırada, dedup."""
    out: list[str] = []
    for c in checks:
        if c == "all":
            return list(ALL_CHECKS)
        if c in ALL_CHECKS and c not in out:
            out.append(c)
    return out or list(ALL_CHECKS)


def find_quality_issues(
    directory: Path | str,
    *,
    config: dict[str, Any],
    checks: Iterable[str] = ("all",),
    recursive: bool = True,
    allowed_exts: Iterable[str] = DEFAULT_IMAGE_EXTS,
    progress_cb: ProgressCallback | None = None,
) -> ScanResult:
    """Bir dizini 4 quality metriği ile tara. Composite QualityResult listesi."""
    root = Path(directory).resolve()
    images = collect_images(root, recursive=recursive, allowed_exts=allowed_exts)
    total = len(images)
    enabled = _resolve_checks(checks)

    if total == 0:
        return ScanResult(
            source_root=str(root),
            total_scanned=0, valid_count=0, invalid_count=0,
            enabled_checks=enabled,
        )

    # Checker'ları başlat (sadece enabled olanlar)
    blur = BlurChecker(config) if "blur" in enabled else None
    bright = BrightnessChecker(config) if "brightness" in enabled else None
    contrast = ContrastChecker(config) if "contrast" in enabled else None
    bpp = BPPChecker(config) if "bpp" in enabled else None

    results: list[dict] = []
    valid_count = invalid_count = 0
    reasons: dict[str, int] = {}

    if progress_cb:
        progress_cb(0, total, "Quality kontrol başlıyor")

    for idx, img in enumerate(images, 1):
        composite = _check_one(img, blur=blur, bright=bright,
                                contrast=contrast, bpp=bpp)
        results.append(composite.to_dict())
        if composite.valid:
            valid_count += 1
        else:
            invalid_count += 1
            for r in (composite.reason or "").split(","):
                r = r.strip()
                if r:
                    reasons[r] = reasons.get(r, 0) + 1

        if progress_cb and (idx % 25 == 0 or idx == total):
            progress_cb(idx, total, f"Quality: {idx}/{total}")

    return ScanResult(
        source_root=str(root),
        total_scanned=total,
        valid_count=valid_count,
        invalid_count=invalid_count,
        enabled_checks=enabled,
        reasons=reasons,
        results=results,
    )


def _check_one(
    image_path: Path,
    *,
    blur: BlurChecker | None,
    bright: BrightnessChecker | None,
    contrast: ContrastChecker | None,
    bpp: BPPChecker | None,
) -> QualityResult:
    """Tek dosyayı enabled checker'lara koştur, composite üret."""
    abs_path = str(image_path.resolve())
    invalid_reasons: list[str] = []

    composite = QualityResult(
        valid=True,
        reason=None,
        filename=image_path.name,
        path=abs_path,
    )

    # File size + dimensions (BPP zaten okur ama her zaman set edelim)
    try:
        composite.file_size_kb = round(image_path.stat().st_size / 1024, 1)
    except OSError:
        pass

    if blur is not None:
        r = blur.check(image_path)
        composite.blur_score = float(r.blur_score)
        composite.is_blurry = r.is_blurry
        if not r.valid:
            invalid_reasons.append(r.reason or "blurry")

    if bright is not None:
        r = bright.check(image_path)
        composite.brightness_score = float(r.brightness)
        composite.brightness_status = (
            "too_dark" if r.is_too_dark
            else "too_bright" if r.is_too_bright
            else "ok"
        )
        if not r.valid:
            invalid_reasons.append(r.reason or "bad_brightness")

    if contrast is not None:
        r = contrast.check(image_path)
        composite.contrast_score = float(r.contrast)
        composite.is_low_contrast = r.is_low_contrast
        if not r.valid:
            invalid_reasons.append(r.reason or "low_contrast")

    if bpp is not None:
        r = bpp.check(image_path)
        composite.bpp_score = round(r.bpp, 4)
        composite.is_over_compressed = r.is_over_compressed
        # Width/height bilgisi BPPResult'tan
        if r.width and r.height:
            composite.width = int(r.width)
            composite.height = int(r.height)
        if not r.valid:
            invalid_reasons.append(r.reason or "over_compressed")

    composite.valid = len(invalid_reasons) == 0
    composite.reason = ",".join(invalid_reasons) if invalid_reasons else None
    return composite
