#!/usr/bin/env python3
"""
Media Quality Checker — CLI

Kullanım örnekleri:
  # Tüm 4 check, sadece raporla (default)
  python run.py -i ./dataset

  # Sadece blur + bpp, recursive
  python run.py -i ./dataset --check blur --check bpp --recursive

  # Düşük-quality'leri /rejected'a taşı (undoable)
  python run.py -i ./dataset --invalid-action move --invalid-dir ./rejected

  # Threshold override
  python run.py -i ./dataset --blur-threshold 50 --min-bpp 0.15

  # Geri al
  python run.py --undo ./rejected/quality_report.json
"""
from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

import yaml

from quality_core import (
    DEFAULT_REPORT_NAME,
    apply_action,
    find_quality_issues,
    undo_from_report,
    write_report,
)


def _print_progress(current: int, total: int, msg: str) -> None:
    if total > 0:
        pct = current * 100 // total
        print(f"\r  {msg} ({pct}%)", end="", flush=True)
    else:
        print(f"\r  {msg}", end="", flush=True)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Media Quality Checker — blur / brightness / contrast / BPP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("-i", "--input", help="Input klasörü (scan modu için zorunlu)")
    p.add_argument("-o", "--output", help=f"JSON rapor yolu (default: <input>/{DEFAULT_REPORT_NAME})")
    p.add_argument("--recursive", action="store_true", default=True,
                   help="Alt klasörleri tara (default: True)")
    p.add_argument("--no-recursive", action="store_false", dest="recursive",
                   help="Sadece üst seviye")
    p.add_argument(
        "--check", action="append", default=[],
        choices=["blur", "brightness", "contrast", "bpp", "all"],
        help="Hangi check çalışsın (tekrar edilebilir; default: all)",
    )
    p.add_argument("--limit", type=int, default=0, help="Max dosya")

    # Aksiyon
    p.add_argument("--invalid-action", choices=["none", "move", "delete"],
                   default="none", help="Düşük-quality dosyalar için aksiyon")
    p.add_argument("--invalid-dir", help="--invalid-action move hedef klasörü")
    p.add_argument("--dry-run", action="store_true",
                   help="Aksiyonu simüle et, dosyaya dokunma")
    p.add_argument("--yes", action="store_true",
                   help="Onay sorma (delete için)")

    # Threshold override
    p.add_argument("--blur-threshold", type=float,
                   help="Laplacian variance eşiği (düşük = bulanık)")
    p.add_argument("--min-brightness", type=float,
                   help="Min ortalama parlaklık (0-255)")
    p.add_argument("--max-brightness", type=float,
                   help="Max ortalama parlaklık (0-255)")
    p.add_argument("--contrast-threshold", type=float,
                   help="Min stddev (düşük = düz)")
    p.add_argument("--min-bpp", type=float,
                   help="Min bytes per pixel")

    # Undo
    p.add_argument("--undo", help="Quality raporundan geri al (move action)")

    p.add_argument("--config", help="settings.yaml yolu")
    return p


def _load_config(path: Path | None) -> dict:
    cfg_path = path or (Path(__file__).parent / "config" / "settings.yaml")
    if not cfg_path.exists():
        if path is not None:
            print(f"Uyarı: config bulunamadı: {cfg_path}", file=sys.stderr)
        return {}
    with open(cfg_path) as f:
        return yaml.safe_load(f) or {}


def _apply_overrides(config: dict, args: argparse.Namespace) -> dict:
    cfg = copy.deepcopy(config)
    quality = cfg.setdefault("quality", {})
    if args.blur_threshold is not None:
        quality["blur_threshold"] = args.blur_threshold
    if args.contrast_threshold is not None:
        quality["contrast_threshold"] = args.contrast_threshold
    if args.min_bpp is not None:
        quality.setdefault("bpp", {})["min"] = args.min_bpp
    if args.min_brightness is not None:
        quality.setdefault("brightness", {})["min"] = args.min_brightness
    if args.max_brightness is not None:
        quality.setdefault("brightness", {})["max"] = args.max_brightness
    return cfg


def _confirm_delete(invalid: int, *, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    print(f"\n⚠  {invalid} dosya KALICI olarak silinecek. Geri alınamaz.")
    answer = input("Devam? [y/N]: ").strip().lower()
    return answer in {"y", "yes", "evet"}


def _run_undo(args: argparse.Namespace) -> int:
    report_path = Path(args.undo)
    if not report_path.exists():
        print(f"Rapor bulunamadı: {report_path}", file=sys.stderr)
        return 1
    print(f"Undo (dry-run={args.dry_run}): {report_path}")
    summary = undo_from_report(report_path, dry_run=args.dry_run)
    print(f"  Restored:               {summary['restored']}")
    print(f"  Skipped:                {summary['skipped']}")
    print(f"  Irreversible (deleted): {summary['irreversible_deletes']}")
    if summary["irreversible_deletes"]:
        print("  → Silinen geri getirilemez (--invalid-action delete kullanılmıştı)")
    return 0


def _resolve_report_path(args: argparse.Namespace, input_dir: Path) -> Path:
    if args.output:
        return Path(args.output)
    if args.invalid_action == "move" and args.invalid_dir:
        return Path(args.invalid_dir) / DEFAULT_REPORT_NAME
    return input_dir / DEFAULT_REPORT_NAME


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.undo:
        if args.input or args.invalid_action != "none":
            parser.error("--undo ile -i/--input veya --invalid-action birlikte kullanılamaz")
        return _run_undo(args)

    if not args.input:
        parser.error("--input gerekli (veya --undo kullan)")

    input_dir = Path(args.input)
    if not input_dir.is_dir():
        print(f"Geçerli dizin değil: {input_dir}", file=sys.stderr)
        return 1

    if args.invalid_action == "move" and not args.invalid_dir:
        parser.error("--invalid-action move için --invalid-dir gerekli")

    config = _load_config(Path(args.config) if args.config else None)
    config = _apply_overrides(config, args)

    checks = args.check or ["all"]

    print(f"\n{'='*70}")
    print(f"Media Quality Checker")
    print(f"{'='*70}")
    print(f"Input:     {input_dir}")
    print(f"Recursive: {args.recursive}")
    print(f"Checks:    {', '.join(checks)}")
    print(f"Action:    {args.invalid_action}{' (DRY-RUN)' if args.dry_run else ''}")
    print(f"{'='*70}\n")

    sr = find_quality_issues(
        input_dir,
        config=config,
        checks=checks,
        recursive=args.recursive,
        progress_cb=_print_progress,
    )
    if args.limit > 0:
        sr.results = sr.results[: args.limit]

    print(f"\n\n{'='*70}\nSONUÇLAR\n{'='*70}")
    print(f"Total:   {sr.total_scanned}")
    print(f"Valid:   {sr.valid_count}")
    print(f"Invalid: {sr.invalid_count}")
    if sr.reasons:
        print("\nReason kırılımı:")
        for reason, count in sorted(sr.reasons.items(), key=lambda x: -x[1]):
            print(f"  - {reason}: {count}")

    # Aksiyon
    if args.invalid_action == "delete" and sr.invalid_count > 0 and not args.dry_run:
        if not _confirm_delete(sr.invalid_count, assume_yes=args.yes):
            print("İptal edildi.")
            return 2

    ar = apply_action(
        sr.results,
        source_root=input_dir,
        action=args.invalid_action,
        invalid_dir=args.invalid_dir,
        dry_run=args.dry_run,
    )

    if args.invalid_action != "none":
        print(f"\nAksiyon: {args.invalid_action}{' (DRY-RUN)' if args.dry_run else ''}")
        if ar.action == "move":
            print(f"  Taşınan: {len(ar.entries)} → {ar.invalid_dir}")
        elif ar.action == "delete":
            print(f"  Silinen: {len(ar.entries)}")
        if ar.skipped:
            print(f"  Atlanan: {ar.skipped}")

    # Rapor
    report_path = _resolve_report_path(args, input_dir)
    write_report(
        report_path,
        scan_result=sr,
        action_result=ar,
        recursive=args.recursive,
        config={"checks": checks, "thresholds": config.get("quality", {})},
    )
    print(f"\nRapor: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
