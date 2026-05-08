"""run.py CLI: argparse + main()."""
import json
import sys
from pathlib import Path

import pytest

from run import _apply_overrides, _build_parser, _resolve_report_path, main


def test_parser_defaults():
    args = _build_parser().parse_args(["-i", "/tmp/x"])
    assert args.input == "/tmp/x"
    assert args.recursive is True
    assert args.invalid_action == "none"
    assert args.check == []  # default boş, sonra 'all'a çevrilir


def test_parser_full_flags():
    args = _build_parser().parse_args([
        "-i", "/tmp/x",
        "--check", "blur", "--check", "bpp",
        "--no-recursive",
        "--blur-threshold", "50",
        "--min-bpp", "0.15",
        "--invalid-action", "move", "--invalid-dir", "/tmp/r",
        "--dry-run", "--yes",
    ])
    assert args.check == ["blur", "bpp"]
    assert args.recursive is False
    assert args.blur_threshold == 50
    assert args.min_bpp == 0.15


def test_apply_overrides_replaces_thresholds():
    cfg = {"quality": {}}
    args = _build_parser().parse_args([
        "-i", "/tmp/x",
        "--blur-threshold", "75",
        "--min-bpp", "0.2",
        "--min-brightness", "40",
        "--max-brightness", "200",
    ])
    out = _apply_overrides(cfg, args)
    q = out["quality"]
    assert q["blur_threshold"] == 75
    assert q["bpp"]["min"] == 0.2
    assert q["brightness"]["min"] == 40
    assert q["brightness"]["max"] == 200


def test_resolve_report_path_explicit(tmp_path: Path):
    args = _build_parser().parse_args(["-i", str(tmp_path), "-o", "/tmp/r.json"])
    assert _resolve_report_path(args, tmp_path) == Path("/tmp/r.json")


def test_resolve_report_path_move_uses_invalid_dir(tmp_path: Path):
    args = _build_parser().parse_args([
        "-i", str(tmp_path),
        "--invalid-action", "move", "--invalid-dir", str(tmp_path / "rej"),
    ])
    out = _resolve_report_path(args, tmp_path)
    assert out == tmp_path / "rej" / "quality_report.json"


def test_main_writes_report(monkeypatch, mixed_dataset: Path):
    monkeypatch.setattr(sys, "argv", [
        "run.py", "-i", str(mixed_dataset),
    ])
    rc = main()
    assert rc == 0
    report = mixed_dataset / "quality_report.json"
    assert report.exists()
    data = json.loads(report.read_text())
    assert data["tool"] == "media-quality-checker"
    assert data["summary"]["total_scanned"] >= 5


def test_main_move_action_e2e(monkeypatch, mixed_dataset: Path, tmp_path_factory):
    rejected = tmp_path_factory.mktemp("rejected")
    monkeypatch.setattr(sys, "argv", [
        "run.py", "-i", str(mixed_dataset),
        "--invalid-action", "move",
        "--invalid-dir", str(rejected),
    ])
    rc = main()
    assert rc == 0
    moved = list(rejected.glob("*.jpg"))
    assert len(moved) >= 3
    assert (rejected / "quality_report.json").exists()


def test_main_undo_cycle(monkeypatch, mixed_dataset: Path, tmp_path_factory):
    rejected = tmp_path_factory.mktemp("rejected")
    monkeypatch.setattr(sys, "argv", [
        "run.py", "-i", str(mixed_dataset),
        "--invalid-action", "move",
        "--invalid-dir", str(rejected),
    ])
    assert main() == 0
    moved_in_rejected = list(rejected.glob("*.jpg"))
    assert moved_in_rejected

    monkeypatch.setattr(sys, "argv", [
        "run.py", "--undo", str(rejected / "quality_report.json"),
    ])
    assert main() == 0
    # Geri taşındı
    assert (mixed_dataset / "blurry.jpg").exists()
    assert not list(rejected.glob("*.jpg"))


def test_main_invalid_dir_required_for_move(monkeypatch, mixed_dataset: Path):
    monkeypatch.setattr(sys, "argv", [
        "run.py", "-i", str(mixed_dataset),
        "--invalid-action", "move",
    ])
    with pytest.raises(SystemExit):
        main()


def test_main_input_required_when_no_undo(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run.py"])
    with pytest.raises(SystemExit):
        main()


def test_main_undo_mutex(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sys, "argv", [
        "run.py", "--undo", str(tmp_path / "x.json"), "-i", "/tmp/y",
    ])
    with pytest.raises(SystemExit):
        main()


def test_main_check_filter(monkeypatch, mixed_dataset: Path):
    """--check blur sadece blur metric'i set eder."""
    monkeypatch.setattr(sys, "argv", [
        "run.py", "-i", str(mixed_dataset), "--check", "blur",
    ])
    rc = main()
    assert rc == 0
    report = json.loads((mixed_dataset / "quality_report.json").read_text())
    assert report["enabled_checks"] == ["blur"]
    # Tüm sonuçlarda sadece blur set olmalı
    for r in report["results"]:
        assert r["blur_score"] is not None
        assert r["brightness_score"] is None
        assert r["bpp_score"] is None
