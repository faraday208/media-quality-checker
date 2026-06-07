"""BlurChecker — tile-based 'en keskin bölge' yöntemi (bokeh/DoF false-positive
önleme) vs global Laplacian variance."""
import numpy as np
from PIL import Image, ImageFilter

from quality_core.checkers.blur_checker import BlurChecker


def _bokeh_image(path, size=256, sharp=56, radius=12):
    """Keskin merkez (özne) + güçlü bulanık kenar (bokeh arkaplan) sentetik görsel."""
    arr = np.random.randint(0, 256, (size, size, 3), dtype=np.uint8)
    sharp_img = Image.fromarray(arr)
    composite = sharp_img.filter(ImageFilter.GaussianBlur(radius=radius))
    c = size // 2
    box = (c - sharp, c - sharp, c + sharp, c + sharp)
    composite.paste(sharp_img.crop(box), (c - sharp, c - sharp))
    composite.save(path, "JPEG", quality=95)
    return path


def test_default_method_is_tile():
    """Default blur yöntemi 'tile' — bokeh portreleri korumak için."""
    c = BlurChecker({"quality": {}})
    assert c.method == "tile"


def test_tile_recovers_sharp_subject_in_bokeh(tmp_path):
    """Keskin özne + bulanık arkaplan: tile yöntemi en keskin bölgeyi yakalar,
    global ortalamadan belirgin yüksek skor verir → bokeh özne 'blurry' damgası
    yemez. (Global yöntem tüm görseli ortaladığı için false-positive riski.)"""
    p = _bokeh_image(tmp_path / "bokeh.jpg")
    cfg_t = {"quality": {"blur_threshold": 100, "blur_method": "tile"}}
    cfg_g = {"quality": {"blur_threshold": 100, "blur_method": "global"}}
    t = BlurChecker(cfg_t).check(p)
    g = BlurChecker(cfg_g).check(p)
    # tile en keskin bölgeyi baz aldığı için global ortalamadan yüksek
    assert t.blur_score > g.blur_score
    # keskin merkez sayesinde bokeh görsel valid (blurry değil)
    assert t.valid is True


def test_tile_still_flags_fully_blurry(tmp_path):
    """Tamamen bulanık görsel: tile yöntemi DE blurry der — kurtaracak keskin
    bölge yok, top-k tile'lar da düşük variance. (False-negative yapmıyor.)"""
    arr = np.random.randint(0, 256, (256, 256, 3), dtype=np.uint8)
    img = Image.fromarray(arr).filter(ImageFilter.GaussianBlur(radius=12))
    p = tmp_path / "blurry.jpg"
    img.save(p, "JPEG", quality=95)
    c = BlurChecker({"quality": {"blur_threshold": 100, "blur_method": "tile"}})
    r = c.check(p)
    assert r.is_blurry is True
    assert r.reason == "blurry"


def test_tile_falls_back_to_global_for_tiny_image(tmp_path):
    """Çok küçük görselde (tile < 8px) global'e düşer — variance gürültüsünden kaçınır."""
    arr = np.random.randint(0, 256, (16, 16, 3), dtype=np.uint8)
    p = tmp_path / "tiny.jpg"
    Image.fromarray(arr).save(p, "JPEG", quality=95)
    c = BlurChecker({"quality": {"blur_method": "tile", "blur_grid": 4}})
    r = c.check(p)  # 16/4 = 4px tile < 8 → global fallback, hata vermemeli
    assert r.blur_score >= 0
