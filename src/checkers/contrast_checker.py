"""
Contrast Checker - Kontrast Kontrolü

Standart sapma ile kontrast ölçümü.
Düşük değer = düz/soluk görüntü.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict


@dataclass
class ContrastResult:
    """Contrast kontrolü sonucu."""
    valid: bool
    reason: Optional[str]
    filename: str
    contrast: float
    threshold: float
    is_low_contrast: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ContrastChecker:
    """Kontrast kontrolü - Standard Deviation."""

    def __init__(self, config: Dict[str, Any]):
        quality_config = config.get('quality', {})
        self.threshold = quality_config.get('contrast_threshold', 15)

    def check(self, image_path: str | Path) -> ContrastResult:
        """
        Tek görüntünün kontrast kontrolü.

        Args:
            image_path: Görüntü dosyası yolu

        Returns:
            ContrastResult
        """
        path = Path(image_path)

        # Hata durumu için
        def error_result(reason: str) -> ContrastResult:
            return ContrastResult(
                valid=False,
                reason=reason,
                filename=path.name,
                contrast=0,
                threshold=self.threshold,
                is_low_contrast=True
            )

        if not path.exists():
            return error_result("file_not_found")

        try:
            # Grayscale olarak oku
            img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if img is None:
                return error_result("cannot_read_image")

            # Standard deviation hesapla
            contrast = float(np.std(img))

            # Değerlendir
            is_low_contrast = bool(contrast < self.threshold)
            valid = not is_low_contrast

            return ContrastResult(
                valid=valid,
                reason="low_contrast" if is_low_contrast else None,
                filename=path.name,
                contrast=round(contrast, 2),
                threshold=self.threshold,
                is_low_contrast=is_low_contrast
            )

        except Exception as e:
            return error_result(f"error: {str(e)[:50]}")

    def check_directory(self, directory: str | Path, limit: int = 0) -> List[ContrastResult]:
        """Klasördeki tüm görselleri kontrol et."""
        dir_path = Path(directory)
        extensions = {'.jpg', '.jpeg', '.png', '.webp'}
        images = [f for f in dir_path.iterdir() if f.is_file() and f.suffix.lower() in extensions]

        if limit > 0:
            images = images[:limit]

        return [self.check(img) for img in images]

    def get_config_summary(self) -> Dict[str, Any]:
        """Config özeti."""
        return {
            "contrast_threshold": self.threshold,
            "method": "standard_deviation"
        }
