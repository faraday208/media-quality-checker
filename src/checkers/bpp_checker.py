"""
BPP Checker - Bytes Per Pixel Kontrolü

Dosya boyutu / piksel sayısı ile sıkıştırma kalitesi ölçümü.
Düşük BPP = aşırı sıkıştırılmış, JPEG artifact'lı görüntü.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from PIL import Image
import os


@dataclass
class BPPResult:
    """BPP kontrolü sonucu."""
    valid: bool
    reason: Optional[str]
    filename: str
    bpp: float
    file_size_kb: float
    width: int
    height: int
    total_pixels: int
    threshold: float
    is_over_compressed: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BPPChecker:
    """Sıkıştırma kalitesi kontrolü - Bytes Per Pixel."""

    def __init__(self, config: Dict[str, Any]):
        quality_config = config.get('quality', {})
        bpp_config = quality_config.get('bpp', {})
        self.min_bpp = bpp_config.get('min', 0.1)

    def check(self, image_path: str | Path) -> BPPResult:
        """
        Tek görüntünün BPP kontrolü.

        Args:
            image_path: Görüntü dosyası yolu

        Returns:
            BPPResult
        """
        path = Path(image_path)

        # Hata durumu için
        def error_result(reason: str) -> BPPResult:
            return BPPResult(
                valid=False,
                reason=reason,
                filename=path.name,
                bpp=0,
                file_size_kb=0,
                width=0,
                height=0,
                total_pixels=0,
                threshold=self.min_bpp,
                is_over_compressed=True
            )

        if not path.exists():
            return error_result("file_not_found")

        try:
            # Dosya boyutu
            file_size = os.path.getsize(path)
            file_size_kb = file_size / 1024

            # Görüntü boyutları
            with Image.open(path) as img:
                width, height = img.size

            # BPP hesapla
            total_pixels = width * height
            bpp = file_size / total_pixels if total_pixels > 0 else 0

            # Değerlendir
            is_over_compressed = bpp < self.min_bpp
            valid = not is_over_compressed

            return BPPResult(
                valid=valid,
                reason="over_compressed" if is_over_compressed else None,
                filename=path.name,
                bpp=round(bpp, 4),
                file_size_kb=round(file_size_kb, 1),
                width=width,
                height=height,
                total_pixels=total_pixels,
                threshold=self.min_bpp,
                is_over_compressed=is_over_compressed
            )

        except Exception as e:
            return error_result(f"error: {str(e)[:50]}")

    def check_directory(self, directory: str | Path, limit: int = 0) -> List[BPPResult]:
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
            "min_bpp": self.min_bpp,
            "method": "file_size_per_pixel"
        }
