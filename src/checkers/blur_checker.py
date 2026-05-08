"""
Blur Checker - Bulanıklık Kontrolü

Laplacian variance yöntemi ile keskinlik ölçümü.
Düşük değer = bulanık görüntü.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict


@dataclass
class BlurResult:
    """Blur kontrolü sonucu."""
    valid: bool
    reason: Optional[str]
    filename: str
    blur_score: float
    threshold: float
    is_blurry: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BlurChecker:
    """Bulanıklık kontrolü - Laplacian Variance."""

    def __init__(self, config: Dict[str, Any]):
        quality_config = config.get('quality', {})
        self.threshold = quality_config.get('blur_threshold', 100)

    def check(self, image_path: str | Path) -> BlurResult:
        """
        Tek görüntünün bulanıklık kontrolü.

        Args:
            image_path: Görüntü dosyası yolu

        Returns:
            BlurResult
        """
        path = Path(image_path)

        # Hata durumu için
        def error_result(reason: str) -> BlurResult:
            return BlurResult(
                valid=False,
                reason=reason,
                filename=path.name,
                blur_score=0,
                threshold=self.threshold,
                is_blurry=True
            )

        if not path.exists():
            return error_result("file_not_found")

        try:
            # Grayscale olarak oku
            img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if img is None:
                return error_result("cannot_read_image")

            # Laplacian variance hesapla
            laplacian = cv2.Laplacian(img, cv2.CV_64F)
            blur_score = laplacian.var()

            # Değerlendir
            is_blurry = bool(blur_score < self.threshold)
            valid = not is_blurry

            return BlurResult(
                valid=valid,
                reason="blurry" if is_blurry else None,
                filename=path.name,
                blur_score=round(float(blur_score), 2),
                threshold=self.threshold,
                is_blurry=is_blurry
            )

        except Exception as e:
            return error_result(f"error: {str(e)[:50]}")

    def check_directory(self, directory: str | Path, limit: int = 0) -> List[BlurResult]:
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
            "blur_threshold": self.threshold,
            "method": "laplacian_variance"
        }
