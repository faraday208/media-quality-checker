"""
Metadata Processor - EXIF/Metadata İşleme

Görevler:
1. EXIF rotation düzeltme (auto_orient)
2. Metadata okuma (analiz için)
3. Metadata temizleme (strip)
4. sRGB color profile dönüşümü
"""

import io
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
from PIL import Image, ImageOps, ExifTags
from PIL.ExifTags import TAGS, GPSTAGS


@dataclass
class MetadataInfo:
    """Okunan metadata bilgisi."""
    has_exif: bool
    orientation: Optional[int]
    camera_make: Optional[str]
    camera_model: Optional[str]
    software: Optional[str]
    datetime: Optional[str]
    has_gps: bool
    has_icc_profile: bool
    icc_profile_name: Optional[str]
    color_mode: str
    original_size: Tuple[int, int]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MetadataResult:
    """Metadata işleme sonucu."""
    success: bool
    reason: Optional[str]
    filename: str
    metadata_info: Optional[MetadataInfo]
    rotation_applied: bool
    metadata_stripped: bool
    color_converted: bool
    new_size: Optional[Tuple[int, int]]
    file_size_reduction_bytes: int

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if self.metadata_info:
            result['metadata_info'] = self.metadata_info.to_dict()
        return result


class MetadataProcessor:
    """Metadata işleme - EXIF düzeltme, temizleme, renk dönüşümü."""

    def __init__(self, config: Dict[str, Any] = None):
        """
        Args:
            config: Opsiyonel ayarlar
        """
        config = config or {}
        metadata_config = config.get('metadata', {})

        # İşlem ayarları
        self.auto_orient = metadata_config.get('auto_orient', True)
        self.strip_metadata = metadata_config.get('strip_metadata', True)
        self.convert_to_srgb = metadata_config.get('convert_to_srgb', True)
        self.preserve_icc = metadata_config.get('preserve_icc', False)

        # sRGB profil (standart)
        self._srgb_profile = None

    def read_metadata(self, image_path: str | Path) -> Optional[MetadataInfo]:
        """
        Görüntüden metadata oku (değiştirmeden).

        Args:
            image_path: Görüntü dosyası yolu

        Returns:
            MetadataInfo veya None (hata durumunda)
        """
        path = Path(image_path)

        try:
            with Image.open(path) as img:
                # EXIF bilgileri
                exif_data = img._getexif() if hasattr(img, '_getexif') else None
                has_exif = exif_data is not None

                orientation = None
                camera_make = None
                camera_model = None
                software = None
                datetime_taken = None
                has_gps = False

                if exif_data:
                    # EXIF tag'lerini parse et
                    for tag_id, value in exif_data.items():
                        tag_name = TAGS.get(tag_id, tag_id)

                        if tag_name == 'Orientation':
                            orientation = value
                        elif tag_name == 'Make':
                            camera_make = str(value).strip()
                        elif tag_name == 'Model':
                            camera_model = str(value).strip()
                        elif tag_name == 'Software':
                            software = str(value).strip()
                        elif tag_name == 'DateTime':
                            datetime_taken = str(value)
                        elif tag_name == 'GPSInfo':
                            has_gps = True

                # ICC profil kontrolü
                icc_profile = img.info.get('icc_profile')
                has_icc = icc_profile is not None
                icc_name = None

                if has_icc:
                    try:
                        # ICC profil adını çıkar (basit yöntem)
                        icc_bytes = icc_profile
                        if len(icc_bytes) > 80:
                            # Profil adı genelde 84. byte'tan başlar
                            icc_name = icc_bytes[84:116].decode('utf-8', errors='ignore').strip('\x00')
                    except Exception:
                        icc_name = "unknown"

                return MetadataInfo(
                    has_exif=has_exif,
                    orientation=orientation,
                    camera_make=camera_make,
                    camera_model=camera_model,
                    software=software,
                    datetime=datetime_taken,
                    has_gps=has_gps,
                    has_icc_profile=has_icc,
                    icc_profile_name=icc_name,
                    color_mode=img.mode,
                    original_size=img.size
                )

        except Exception as e:
            return None

    def process(self, image_path: str | Path) -> Tuple[Optional[Image.Image], MetadataResult]:
        """
        Görüntüyü işle: rotation düzelt, metadata temizle, renk dönüştür.

        Args:
            image_path: Görüntü dosyası yolu

        Returns:
            (İşlenmiş PIL Image, MetadataResult) tuple'ı
        """
        path = Path(image_path)

        def error_result(reason: str) -> Tuple[None, MetadataResult]:
            return None, MetadataResult(
                success=False,
                reason=reason,
                filename=path.name,
                metadata_info=None,
                rotation_applied=False,
                metadata_stripped=False,
                color_converted=False,
                new_size=None,
                file_size_reduction_bytes=0
            )

        if not path.exists():
            return error_result("file_not_found")

        try:
            # Orijinal dosya boyutu
            original_file_size = path.stat().st_size

            # Metadata oku
            metadata_info = self.read_metadata(path)

            # Görüntüyü aç
            img = Image.open(path)
            original_size = img.size

            rotation_applied = False
            color_converted = False

            # 1. EXIF rotation düzelt
            if self.auto_orient:
                try:
                    oriented_img = ImageOps.exif_transpose(img)
                    if oriented_img is not None:
                        if oriented_img.size != img.size:
                            rotation_applied = True
                        img = oriented_img
                except Exception:
                    pass  # Rotation başarısız olursa orijinal kullan

            # 2. RGB'ye çevir (RGBA, P, L gibi modları)
            if img.mode not in ('RGB',):
                if img.mode == 'RGBA':
                    # Alpha channel'ı beyaz background ile birleştir
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])
                    img = background
                    color_converted = True
                elif img.mode in ('P', 'L', 'LA'):
                    img = img.convert('RGB')
                    color_converted = True
                else:
                    img = img.convert('RGB')
                    color_converted = True

            # 3. Metadata strip (temiz kopya oluştur)
            metadata_stripped = False
            if self.strip_metadata:
                # Pixel verisini al
                data = list(img.getdata())

                # Yeni temiz image oluştur
                clean_img = Image.new('RGB', img.size)
                clean_img.putdata(data)

                img = clean_img
                metadata_stripped = True

            # Boyut tahmini (bellekte)
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=95)
            new_size_bytes = buffer.tell()

            size_reduction = original_file_size - new_size_bytes

            return img, MetadataResult(
                success=True,
                reason=None,
                filename=path.name,
                metadata_info=metadata_info,
                rotation_applied=rotation_applied,
                metadata_stripped=metadata_stripped,
                color_converted=color_converted,
                new_size=img.size,
                file_size_reduction_bytes=max(0, size_reduction)
            )

        except Exception as e:
            return error_result(f"error: {str(e)[:50]}")

    def process_and_save(
        self,
        image_path: str | Path,
        output_path: str | Path,
        quality: int = 95,
        format: str = None
    ) -> MetadataResult:
        """
        Görüntüyü işle ve kaydet.

        Args:
            image_path: Kaynak görüntü yolu
            output_path: Hedef dosya yolu
            quality: JPEG kalitesi (1-100)
            format: Çıktı formatı (None = otomatik)

        Returns:
            MetadataResult
        """
        img, result = self.process(image_path)

        if not result.success or img is None:
            return result

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Format belirle
        if format is None:
            suffix = output_path.suffix.lower()
            if suffix in ('.jpg', '.jpeg'):
                format = 'JPEG'
            elif suffix == '.png':
                format = 'PNG'
            elif suffix == '.webp':
                format = 'WEBP'
            else:
                format = 'JPEG'

        try:
            save_kwargs = {}
            if format == 'JPEG':
                save_kwargs = {'quality': quality, 'optimize': True}
            elif format == 'PNG':
                save_kwargs = {'optimize': True}
            elif format == 'WEBP':
                save_kwargs = {'quality': quality}

            img.save(output_path, format=format, **save_kwargs)

            # Gerçek boyut farkını hesapla
            new_size = output_path.stat().st_size
            original_size = Path(image_path).stat().st_size
            result.file_size_reduction_bytes = max(0, original_size - new_size)

            return result

        except Exception as e:
            return MetadataResult(
                success=False,
                reason=f"save_error: {str(e)[:50]}",
                filename=Path(image_path).name,
                metadata_info=result.metadata_info,
                rotation_applied=result.rotation_applied,
                metadata_stripped=result.metadata_stripped,
                color_converted=result.color_converted,
                new_size=result.new_size,
                file_size_reduction_bytes=0
            )

    def get_config_summary(self) -> Dict[str, Any]:
        """Config özeti."""
        return {
            "auto_orient": self.auto_orient,
            "strip_metadata": self.strip_metadata,
            "convert_to_srgb": self.convert_to_srgb,
            "preserve_icc": self.preserve_icc
        }
