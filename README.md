# media-quality-checker

> Görsel dataset'lerde kalite filtreleme — blur, brightness, contrast, BPP.
> Şu an **görsel** odaklı; video desteği gelecek sürümlerde planlanıyor.
> Düşük-quality dosyaları rapor eder, opsiyonel olarak `/rejected`'a taşır veya siler.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/built%20with-uv-261230)](https://github.com/astral-sh/uv)

`media-dataset-prep` pipeline'ının **03. adımı**. Standalone kullanılabilir.

---

## 🎯 Ne yapıyor?

Composite quality kontrolü — 4 metric:

| Check | Algoritma | Reason kodları |
|---|---|---|
| **blur** | Laplacian variance (cv2) | `blurry` |
| **brightness** | Mean pixel value (0-255) | `too_dark`, `too_bright` |
| **contrast** | Standard deviation | `low_contrast` |
| **bpp** | Bytes per pixel | `over_compressed` |

Her dosya tüm enabled check'lerden geçirilir; **bir bile fail = invalid**, reason composite (`blurry,low_contrast` gibi virgülle).

---

## 🚀 Kurulum

```bash
git clone https://github.com/faraday208/media-quality-checker
cd media-quality-checker
uv sync
```

`media-dataset-prep` workspace'i altında: `make install`

---

## 🛠️ Kullanım — CLI

### Default (tüm 4 check, sadece raporla)

```bash
uv run python run.py -i ./dataset
```

Çıktı: `./dataset/quality_report.json`

### Sadece blur + bpp

```bash
uv run python run.py -i ./dataset --check blur --check bpp
```

### Düşük-quality'leri taşı (undoable)

```bash
uv run python run.py -i ./dataset \
    --invalid-action move \
    --invalid-dir ./rejected
```

### Threshold override

```bash
uv run python run.py -i ./dataset \
    --blur-threshold 50 \
    --min-brightness 40 --max-brightness 220 \
    --min-bpp 0.15
```

### Sil (irreversible — onay sorar)

```bash
uv run python run.py -i ./dataset --invalid-action delete
# veya onay'sız:
uv run python run.py -i ./dataset --invalid-action delete --yes
```

### Geri al (undo)

```bash
uv run python run.py --undo ./rejected/quality_report.json
```

---

## 📋 Operation modes — özet

| Mod | Komut | Etki | Undo |
|---|---|---|---|
| **Sadece rapor** | `--invalid-action none` (default) | Dokunulmaz | – |
| **Move** | `--invalid-action move --invalid-dir D` | Düşük-quality D'ye taşınır | ✓ |
| **Delete** | `--invalid-action delete` | Silinir | ✗ irreversible |
| **Dry-run** | + `--dry-run` | Rapor üretilir, fiziksel değişiklik yok | – |
| **Undo** | `--undo REPORT` | move-action geri alınır | – |

---

## 🚩 Tüm CLI flag'leri

| Flag | Tip | Default | Açıklama |
|---|---|---|---|
| `-i, --input` | str | – | Input klasörü |
| `-o, --output` | str | `<input>/quality_report.json` | Rapor JSON |
| `--recursive` / `--no-recursive` | flag | True | Alt klasör tarama |
| `--check` (multiple) | `blur\|brightness\|contrast\|bpp\|all` | `[all]` | Hangi check'ler çalışsın |
| `--limit N` | int | 0 | Max dosya |
| `--invalid-action` | `none\|move\|delete` | `none` | Düşük-quality aksiyonu |
| `--invalid-dir` | str | – | move hedefi |
| `--dry-run` | flag | False | Simüle et |
| `--yes` | flag | False | Onay sorma (delete) |
| `--blur-threshold` | float | 100 | Laplacian variance min |
| `--min-brightness` | float | 30 | Min ortalama pixel |
| `--max-brightness` | float | 225 | Max ortalama pixel |
| `--contrast-threshold` | float | 15 | Min stddev |
| `--min-bpp` | float | 0.1 | Min bytes per pixel |
| `--undo` | str | – | Quality raporundan undo |
| `--config` | str | `config/settings.yaml` | Config yolu |

---

## ⚙️ Config — `config/settings.yaml`

```yaml
quality:
  blur_threshold: 100      # Laplacian variance — düşük = bulanık
  brightness:
    min: 30                # Altı çok karanlık
    max: 225               # Üstü çok parlak
  contrast_threshold: 15   # Stddev — düşük = düz
  bpp:
    min: 0.1               # Bytes per pixel
```

CLI flag'leri her zaman ezer.

---

## 🔌 In-process (library) kullanım

```python
from quality_core import (
    find_quality_issues, apply_action, undo_from_report, write_report,
    BlurChecker, BPPChecker, BrightnessChecker, ContrastChecker,
)

config = {"quality": {"blur_threshold": 80, "bpp": {"min": 0.15}}}

# Composite scan
sr = find_quality_issues("./dataset", config=config, checks=["all"], recursive=True)
print(f"{sr.invalid_count}/{sr.total_scanned} invalid")
print(f"Reasons: {sr.reasons}")

# Aksiyon (opsiyonel)
ar = apply_action(
    sr.results,
    source_root="./dataset",
    action="move",
    invalid_dir="./rejected",
)

# Rapor + undo
write_report("./rejected/quality_report.json",
             scan_result=sr, action_result=ar,
             recursive=True, config={"checks": ["all"]})

# Tek dosya — eski API hâlâ çalışıyor
blur = BlurChecker(config)
print(blur.check("./img.jpg").to_dict())
```

`media-dataset-prep` meta UI bu yolla in-process kullanır.

---

## 📄 Rapor formatı

```jsonc
{
  "version": "1",
  "tool": "media-quality-checker",
  "source_root": "/abs/path",
  "recursive": true,
  "enabled_checks": ["blur", "brightness", "contrast", "bpp"],
  "config": { "checks": ["all"], "thresholds": {...} },
  "summary": {
    "total_scanned": 100, "valid": 87, "invalid": 13,
    "reasons": {"blurry": 8, "too_dark": 3, "low_contrast,blurry": 2}
  },
  "action": "move",
  "invalid_dir": "/abs/.../rejected",
  "actions": [
    {"original": "/abs/.../bad.jpg", "moved_to": "/abs/rejected/bad.jpg",
     "reason": "blurry,low_contrast"}
  ],
  "skipped": 0,
  "results": [
    {"valid": false, "reason": "blurry", "filename": "x.jpg",
     "path": "/abs/.../x.jpg", "width": 1024, "height": 768,
     "blur_score": 45.2, "is_blurry": true,
     "brightness_score": 128, "brightness_status": "ok",
     "contrast_score": 42.1, "is_low_contrast": false,
     "bpp_score": 0.345, "is_over_compressed": false}
  ]
}
```

---

## 🧪 Test

```bash
uv sync --group dev
uv run pytest
```

44 test: scanner (composite + her check tipi), actions (move/delete/undo), CLI e2e.

---

## ⚠️ Limitations

- `--invalid-action delete` **irreversible** — silinen geri gelmez
- Recursive move'da invalid'ler `invalid_dir` altına **flat** iner (alt klasör hiyerarşisi korunmaz; isim çakışması `_1`, `_2` ile)
- `cv2` (opencv-python) gerekli — büyük dependency (~100 MB), CI'da headless versiyon: `opencv-python-headless`
- Şu an sadece **görsel** quality. Video frame quality (frame extract + her frame check) planlı

---

## 🏷️ Sürüm

**v1.0.0** — clean release. `image-quality-checker` → `media-quality-checker`. Convention §uyumlu refactor:
- click subcommand → argparse + standart flag'ler
- Tek-dosya `check IMG` → toplu `find_quality_issues(directory)` (recursive)
- Sidecar JSON + action layer (move/delete) + undo
- Composite scanner (4 checker → 1 sonuç, virgülle reason)
- README 8 bölüm, MIT LICENSE, 44 test
- `config.py` API kalıntıları (server/n8n) temizlendi
- BlurChecker / BPPChecker / vs. tek-dosya API'si korundu (geriye uyum)

---

## 📜 Lisans

[MIT](LICENSE)
