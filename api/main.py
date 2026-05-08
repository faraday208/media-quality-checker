"""
Image Quality Checker API
Blur, Brightness, Contrast, BPP kontrolü.
"""

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from pathlib import Path
import yaml
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.checkers import (
    BlurChecker, BlurResult,
    BrightnessChecker, BrightnessResult,
    ContrastChecker, ContrastResult,
    BPPChecker, BPPResult,
    MetadataProcessor, MetadataResult, MetadataInfo
)

# Load config
CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"


def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f)
    return {}


config = load_config()

# Quality checkers
blur_checker = BlurChecker(config)
brightness_checker = BrightnessChecker(config)
contrast_checker = ContrastChecker(config)
bpp_checker = BPPChecker(config)
metadata_processor = MetadataProcessor(config)

# FastAPI app
app = FastAPI(
    title="Image Quality Checker API",
    description="Görüntü kalite kontrolü: Blur, Brightness, Contrast, BPP, Metadata",
    version="1.1.0"
)


# ============================================================
# Request Models
# ============================================================

class DirectoryRequest(BaseModel):
    """Klasör tarama için request."""
    directory: str = Field(..., description="Klasör yolu")
    limit: int = Field(0, description="Max dosya sayısı (0=unlimited)")


class SaveReportRequest(BaseModel):
    """Rapor kaydetme için request."""
    directory: str = Field(..., description="Ana klasör yolu")
    sub_directory: str = Field("reports", description="Alt klasör adı")
    content: Any = Field(..., description="Rapor içeriği (dict veya string)")
    filename: Optional[str] = Field(None, description="Dosya adı (opsiyonel, auto-generate)")
    filename_prefix: str = Field("report", description="Dosya adı prefix'i")


class MetadataProcessRequest(BaseModel):
    """Metadata işleme ve kaydetme için request."""
    input_path: str = Field(..., description="Kaynak dosya yolu")
    output_path: str = Field(..., description="Hedef dosya yolu")
    quality: int = Field(95, description="JPEG kalitesi (1-100)")
    format: Optional[str] = Field(None, description="Çıktı formatı (JPEG, PNG, WEBP)")


class MoveFileRequest(BaseModel):
    """Dosya taşıma için request."""
    source_path: str = Field(..., description="Kaynak dosya yolu")
    target_directory: str = Field(..., description="Hedef klasör yolu")
    create_directory: bool = Field(True, description="Klasör yoksa oluştur")


# ============================================================
# Health & Info
# ============================================================

@app.get("/")
async def root():
    """API durumu ve config bilgisi."""
    return {
        "status": "ok",
        "version": "1.1.0",
        "service": "dataset-prep/03-quality",
        "checks": ["blur", "brightness", "contrast", "bpp", "metadata"],
        "config": {
            "blur": blur_checker.get_config_summary(),
            "brightness": brightness_checker.get_config_summary(),
            "contrast": contrast_checker.get_config_summary(),
            "bpp": bpp_checker.get_config_summary(),
            "metadata": metadata_processor.get_config_summary()
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/config")
async def get_config():
    """Tüm config bilgisini döndür."""
    return {
        "blur": blur_checker.get_config_summary(),
        "brightness": brightness_checker.get_config_summary(),
        "contrast": contrast_checker.get_config_summary(),
        "bpp": bpp_checker.get_config_summary(),
        "metadata": metadata_processor.get_config_summary(),
        "raw_config": config
    }


# ============================================================
# BLUR Endpoints
# ============================================================

@app.post("/blur")
async def check_blur(path: str = Query(..., description="Dosya yolu")):
    """Blur kontrolü - tek dosya."""
    if not Path(path).exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    result = blur_checker.check(path)
    return result.to_dict()


@app.post("/blur/directory")
async def check_blur_directory(request: DirectoryRequest):
    """Blur kontrolü - klasör."""
    if not Path(request.directory).exists():
        raise HTTPException(status_code=404, detail=f"Directory not found: {request.directory}")
    results = blur_checker.check_directory(request.directory, request.limit)
    valid_count = sum(1 for r in results if r.valid)
    return {
        "total": len(results),
        "valid_count": valid_count,
        "invalid_count": len(results) - valid_count,
        "config_used": blur_checker.get_config_summary(),
        "results": [r.to_dict() for r in results]
    }


# ============================================================
# BRIGHTNESS Endpoints
# ============================================================

@app.post("/brightness")
async def check_brightness(path: str = Query(..., description="Dosya yolu")):
    """Brightness kontrolü - tek dosya."""
    if not Path(path).exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    result = brightness_checker.check(path)
    return result.to_dict()


@app.post("/brightness/directory")
async def check_brightness_directory(request: DirectoryRequest):
    """Brightness kontrolü - klasör."""
    if not Path(request.directory).exists():
        raise HTTPException(status_code=404, detail=f"Directory not found: {request.directory}")
    results = brightness_checker.check_directory(request.directory, request.limit)
    valid_count = sum(1 for r in results if r.valid)
    return {
        "total": len(results),
        "valid_count": valid_count,
        "invalid_count": len(results) - valid_count,
        "config_used": brightness_checker.get_config_summary(),
        "results": [r.to_dict() for r in results]
    }


# ============================================================
# CONTRAST Endpoints
# ============================================================

@app.post("/contrast")
async def check_contrast(path: str = Query(..., description="Dosya yolu")):
    """Contrast kontrolü - tek dosya."""
    if not Path(path).exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    result = contrast_checker.check(path)
    return result.to_dict()


@app.post("/contrast/directory")
async def check_contrast_directory(request: DirectoryRequest):
    """Contrast kontrolü - klasör."""
    if not Path(request.directory).exists():
        raise HTTPException(status_code=404, detail=f"Directory not found: {request.directory}")
    results = contrast_checker.check_directory(request.directory, request.limit)
    valid_count = sum(1 for r in results if r.valid)
    return {
        "total": len(results),
        "valid_count": valid_count,
        "invalid_count": len(results) - valid_count,
        "config_used": contrast_checker.get_config_summary(),
        "results": [r.to_dict() for r in results]
    }


# ============================================================
# BPP Endpoints
# ============================================================

@app.post("/bpp")
async def check_bpp(path: str = Query(..., description="Dosya yolu")):
    """BPP kontrolü - tek dosya."""
    if not Path(path).exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    result = bpp_checker.check(path)
    return result.to_dict()


@app.post("/bpp/directory")
async def check_bpp_directory(request: DirectoryRequest):
    """BPP kontrolü - klasör."""
    if not Path(request.directory).exists():
        raise HTTPException(status_code=404, detail=f"Directory not found: {request.directory}")
    results = bpp_checker.check_directory(request.directory, request.limit)
    valid_count = sum(1 for r in results if r.valid)
    return {
        "total": len(results),
        "valid_count": valid_count,
        "invalid_count": len(results) - valid_count,
        "config_used": bpp_checker.get_config_summary(),
        "results": [r.to_dict() for r in results]
    }


# ============================================================
# METADATA Endpoints
# ============================================================

@app.post("/metadata/read")
async def read_metadata(path: str = Query(..., description="Dosya yolu")):
    """Metadata oku - dosyayı değiştirmeden sadece bilgi al."""
    if not Path(path).exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    result = metadata_processor.read_metadata(path)
    if result is None:
        raise HTTPException(status_code=400, detail="Could not read metadata")
    return result.to_dict()


@app.post("/metadata/process")
async def process_metadata(path: str = Query(..., description="Dosya yolu")):
    """Metadata işle - rotation düzelt, metadata temizle (bellekte, kaydetmez)."""
    if not Path(path).exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    img, result = metadata_processor.process(path)
    return result.to_dict()


@app.post("/metadata/process-and-save")
async def process_and_save_metadata(request: MetadataProcessRequest):
    """Metadata işle ve kaydet - rotation düzelt, metadata temizle, dosyaya yaz."""
    if not Path(request.input_path).exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.input_path}")
    result = metadata_processor.process_and_save(
        request.input_path,
        request.output_path,
        quality=request.quality,
        format=request.format
    )
    return result.to_dict()


@app.post("/metadata/directory")
async def process_metadata_directory(request: DirectoryRequest):
    """Metadata kontrolü - klasör (sadece okuma, değişiklik yapmaz)."""
    if not Path(request.directory).exists():
        raise HTTPException(status_code=404, detail=f"Directory not found: {request.directory}")

    dir_path = Path(request.directory)
    extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    images = [f for f in dir_path.iterdir() if f.is_file() and f.suffix.lower() in extensions]

    if request.limit > 0:
        images = images[:request.limit]

    results = []
    stats = {
        "has_exif": 0,
        "needs_rotation": 0,
        "has_gps": 0,
        "has_icc_profile": 0,
        "non_rgb": 0
    }

    for img_path in images:
        info = metadata_processor.read_metadata(img_path)
        if info:
            result = {"filename": img_path.name, **info.to_dict()}
            results.append(result)

            # İstatistikler
            if info.has_exif:
                stats["has_exif"] += 1
            if info.orientation and info.orientation != 1:
                stats["needs_rotation"] += 1
            if info.has_gps:
                stats["has_gps"] += 1
            if info.has_icc_profile:
                stats["has_icc_profile"] += 1
            if info.color_mode != "RGB":
                stats["non_rgb"] += 1

    return {
        "total": len(results),
        "stats": stats,
        "config_used": metadata_processor.get_config_summary(),
        "results": results
    }


# ============================================================
# UTILS Endpoints
# ============================================================

@app.post("/save-report")
async def save_report(request: SaveReportRequest):
    """Rapor dosyası kaydet."""
    import json
    from datetime import datetime

    # Full directory path
    full_dir = Path(request.directory) / request.sub_directory

    # Create directory if not exists
    full_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename if not provided
    if request.filename:
        filename = request.filename
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{request.filename_prefix}_{timestamp}.json"

    filepath = full_dir / filename

    # Write content
    content = request.content
    if isinstance(content, dict) or isinstance(content, list):
        content_str = json.dumps(content, indent=2, ensure_ascii=False)
    else:
        content_str = str(content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content_str)

    return {
        "success": True,
        "filepath": str(filepath),
        "filename": filename,
        "directory": request.directory,
        "sub_directory": request.sub_directory
    }


@app.post("/move-file")
async def move_file(request: MoveFileRequest):
    """Dosyayı hedef klasöre taşı."""
    import shutil

    source = Path(request.source_path)

    if not source.exists():
        raise HTTPException(status_code=404, detail=f"Source file not found: {request.source_path}")

    target_dir = Path(request.target_directory)

    if request.create_directory:
        target_dir.mkdir(parents=True, exist_ok=True)
    elif not target_dir.exists():
        raise HTTPException(status_code=404, detail=f"Target directory not found: {request.target_directory}")

    target_path = target_dir / source.name

    try:
        shutil.move(str(source), str(target_path))
        return {
            "success": True,
            "source": str(source),
            "target": str(target_path),
            "filename": source.name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Move failed: {str(e)}")


# ============================================================
# Run
# ============================================================

if __name__ == "__main__":
    import uvicorn

    host = config.get('server', {}).get('host', '0.0.0.0')
    port = config.get('server', {}).get('port', 8101)

    print(f"Starting Image Quality Checker API on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
