"""
Brightness Checker - Parlaklık Kontrolü

Mean pixel value ile parlaklık ölçümü.
Çok düşük = karanlık, çok yüksek = yanık/overexposed.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict


@dataclass
class BrightnessResult:
    """Brightness kontrolü sonucu."""
    valid: bool
    reason: Optional[str]
    filename: str
    brightness: float
    min_threshold: float
    max_threshold: float
    is_too_dark: bool
    is_too_bright: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BrightnessChecker:
    """Parlaklık kontrolü - Mean Pixel Value."""

    def __init__(self, config: Dict[str, Any]):
        quality_config = config.get('quality', {})
        brightness_config = quality_config.get('brightness', {})
        self.min_threshold = brightness_config.get('min', 30)
        self.max_threshold = brightness_config.get('max', 225)

    def check(self, image_path: str | Path) -> BrightnessResult:
        """
        Tek görüntünün parlaklık kontrolü.

        Args:
            image_path: Görüntü dosyası yolu

        Returns:
            BrightnessResult
        """
        path = Path(image_path)

        # Hata durumu için
        def error_result(reason: str) -> BrightnessResult:
            return BrightnessResult(
                valid=False,
                reason=reason,
                filename=path.name,
                brightness=0,
                min_threshold=self.min_threshold,
                max_threshold=self.max_threshold,
                is_too_dark=False,
                is_too_bright=False
            )

        if not path.exists():
            return error_result("file_not_found")

        try:
            # Grayscale olarak oku
            img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if img is None:
                return error_result("cannot_read_image")

            # Mean brightness hesapla
            brightness = float(np.mean(img))

            # Değerlendir
            is_too_dark = bool(brightness < self.min_threshold)
            is_too_bright = bool(brightness > self.max_threshold)
            valid = not (is_too_dark or is_too_bright)

            reason = None
            if is_too_dark:
                reason = "too_dark"
            elif is_too_bright:
                reason = "too_bright"

            return BrightnessResult(
                valid=valid,
                reason=reason,
                filename=path.name,
                brightness=round(brightness, 2),
                min_threshold=self.min_threshold,
                max_threshold=self.max_threshold,
                is_too_dark=is_too_dark,
                is_too_bright=is_too_bright
            )

        except Exception as e:
            return error_result(f"error: {str(e)[:50]}")

    def check_directory(self, directory: str | Path, limit: int = 0) -> List[BrightnessResult]:
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
            "brightness_min": self.min_threshold,
            "brightness_max": self.max_threshold,
            "method": "mean_pixel_value"
        }
