"""Actions: apply_action (move/delete) + undo."""
from pathlib import Path

import pytest

from quality_core import (
    apply_action,
    find_quality_issues,
    undo_from_report,
    write_report,
)


def _scan(dataset: Path, cfg: dict):
    return find_quality_issues(dataset, config=cfg, recursive=True)


def test_action_none_no_changes(mixed_dataset: Path, quality_config: dict):
    sr = _scan(mixed_dataset, quality_config)
    ar = apply_action(sr.results, source_root=mixed_dataset, action="none")
    assert ar.entries == []
    assert (mixed_dataset / "blurry.jpg").exists()


def test_action_move_relocates_invalid(mixed_dataset: Path, tmp_path_factory,
                                        quality_config: dict):
    rejected = tmp_path_factory.mktemp("rejected")
    sr = _scan(mixed_dataset, quality_config)
    ar = apply_action(sr.results, source_root=mixed_dataset,
                      action="move", invalid_dir=rejected)
    # invalid'ler taşındı
    assert len(ar.entries) >= 3  # blurry, dark, bright (en az)
    # Valid'ler yerinde
    assert (mixed_dataset / "normal.jpg").exists()
    # Rejected'a taşındı
    moved_names = {Path(e.moved_to).name for e in ar.entries}
    assert "blurry.jpg" in moved_names
    assert "dark.jpg" in moved_names


def test_action_move_dry_run_no_filesystem_change(mixed_dataset: Path, tmp_path_factory,
                                                    quality_config: dict):
    rejected = tmp_path_factory.mktemp("rejected")
    sr = _scan(mixed_dataset, quality_config)
    ar = apply_action(sr.results, source_root=mixed_dataset,
                      action="move", invalid_dir=rejected, dry_run=True)
    # Log var, dosyalar yerinde
    assert len(ar.entries) >= 3
    assert (mixed_dataset / "blurry.jpg").exists()
    assert not list(rejected.iterdir())


def test_action_delete_removes_invalid(mixed_dataset: Path, quality_config: dict):
    sr = _scan(mixed_dataset, quality_config)
    ar = apply_action(sr.results, source_root=mixed_dataset, action="delete")
    assert all(e.deleted for e in ar.entries)
    assert not (mixed_dataset / "blurry.jpg").exists()
    # Valid'ler yerinde
    assert (mixed_dataset / "normal.jpg").exists()


def test_action_delete_dry_run_no_changes(mixed_dataset: Path, quality_config: dict):
    sr = _scan(mixed_dataset, quality_config)
    ar = apply_action(sr.results, source_root=mixed_dataset,
                      action="delete", dry_run=True)
    assert len(ar.entries) >= 3
    assert (mixed_dataset / "blurry.jpg").exists()


def test_action_move_requires_invalid_dir(mixed_dataset: Path, quality_config: dict):
    sr = _scan(mixed_dataset, quality_config)
    with pytest.raises(ValueError, match="invalid_dir"):
        apply_action(sr.results, source_root=mixed_dataset,
                     action="move", invalid_dir=None)


def test_action_invalid_value_raises(mixed_dataset: Path, quality_config: dict):
    sr = _scan(mixed_dataset, quality_config)
    with pytest.raises(ValueError, match="action"):
        apply_action(sr.results, source_root=mixed_dataset, action="burn")


def test_action_skips_unknown_filename(tmp_path: Path):
    res = apply_action(
        [{"valid": False, "filename": "ghost.jpg", "reason": "test", "path": ""}],
        source_root=tmp_path, action="delete",
    )
    assert res.entries == []
    assert res.skipped == 1


# ---------- Undo ----------

def test_undo_restores_moved(mixed_dataset: Path, tmp_path_factory,
                              quality_config: dict):
    rejected = tmp_path_factory.mktemp("rejected")
    sr = _scan(mixed_dataset, quality_config)
    ar = apply_action(sr.results, source_root=mixed_dataset,
                      action="move", invalid_dir=rejected)
    report = rejected / "quality_report.json"
    write_report(report, scan_result=sr, action_result=ar,
                 recursive=True, config={"checks": ["all"]})
    summary = undo_from_report(report)
    assert summary["restored"] == len(ar.entries)
    assert (mixed_dataset / "blurry.jpg").exists()


def test_undo_dry_run(mixed_dataset: Path, tmp_path_factory, quality_config: dict):
    rejected = tmp_path_factory.mktemp("rejected")
    sr = _scan(mixed_dataset, quality_config)
    ar = apply_action(sr.results, source_root=mixed_dataset,
                      action="move", invalid_dir=rejected)
    report = rejected / "quality_report.json"
    write_report(report, scan_result=sr, action_result=ar,
                 recursive=True, config={"checks": ["all"]})
    summary = undo_from_report(report, dry_run=True)
    assert summary["restored"] == len(ar.entries)
    # Dosyalar hala rejected'ta
    assert not (mixed_dataset / "blurry.jpg").exists()


def test_undo_irreversible_for_delete(mixed_dataset: Path, tmp_path: Path,
                                       quality_config: dict):
    sr = _scan(mixed_dataset, quality_config)
    ar = apply_action(sr.results, source_root=mixed_dataset, action="delete")
    report = tmp_path / "report.json"
    write_report(report, scan_result=sr, action_result=ar,
                 recursive=True, config={"checks": ["all"]})
    summary = undo_from_report(report)
    assert summary["irreversible_deletes"] == len(ar.entries)
    assert summary["restored"] == 0


def test_undo_rejects_wrong_tool(tmp_path: Path):
    import json
    report = tmp_path / "fake.json"
    report.write_text(json.dumps({"tool": "other", "actions": []}))
    with pytest.raises(ValueError, match="tool mismatch"):
        undo_from_report(report)
