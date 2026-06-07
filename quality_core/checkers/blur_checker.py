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
        # Blur ölçüm yöntemi:
        #   'tile'   (default) — görseli grid'e böl, EN KESKİN bölgeleri baz al.
        #            Bokeh/DoF arkaplan keskin özneyi cezalandırmaz (false-positive'i
        #            önler). "Görselin bir yeri keskin mi?" sorusu.
        #   'global' — tüm görselin Laplacian variance'ı (eski davranış). Bulanık
        #            arkaplan skoru düşürür → bokeh portreleri yanlışlıkla eleyebilir.
        self.method = quality_config.get('blur_method', 'tile')
        self.grid = int(quality_config.get('blur_grid', 4))          # 4x4 = 16 tile
        self.top_k = int(quality_config.get('blur_top_k', 4))        # en keskin 4 tile

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

            # Blur skoru — yöntem'e göre (tile: en keskin bölge / global: tüm görsel)
            blur_score = self._compute_blur_score(img)

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

    def _compute_blur_score(self, img: np.ndarray) -> float:
        """Laplacian variance — yöntem'e göre. 'global' tüm görsel; 'tile' grid'e
        bölüp en keskin top_k tile'ın ortalaması (bokeh arkaplan özneyi
        cezalandırmaz)."""
        if self.method == 'global' or self.grid <= 1:
            return round(float(cv2.Laplacian(img, cv2.CV_64F).var()), 2)

        h, w = img.shape[:2]
        th, tw = h // self.grid, w // self.grid
        # Tile'lar çok küçükse (variance gürültülü/anlamsız) global'e düş
        if th < 8 or tw < 8:
            return round(float(cv2.Laplacian(img, cv2.CV_64F).var()), 2)

        scores: List[float] = []
        for i in range(self.grid):
            for j in range(self.grid):
                tile = img[i * th:(i + 1) * th, j * tw:(j + 1) * tw]
                scores.append(float(cv2.Laplacian(tile, cv2.CV_64F).var()))
        scores.sort(reverse=True)
        k = max(1, min(self.top_k, len(scores)))
        return round(sum(scores[:k]) / k, 2)

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
        summary = {
            "blur_threshold": self.threshold,
            "method": f"laplacian_variance/{self.method}",
        }
        if self.method == 'tile':
            summary["grid"] = self.grid
            summary["top_k"] = self.top_k
        return summary
