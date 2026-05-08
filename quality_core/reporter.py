"""
Reporter — sidecar JSON (tool-conventions §4 uyumlu).

{
  "version": "1",
  "tool": "media-quality-checker",
  "source_root": "/abs/path",
  "recursive": bool,
  "enabled_checks": [...],
  "config": {...},
  "summary": {total_scanned, valid, invalid, reasons{...}},
  "action": "none|move|delete",
  "invalid_dir": ...,
  "actions": [...],
  "skipped": int,
  "results": [...]
}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .actions import ActionResult
from .scanner import ScanResult

REPORT_VERSION = "1"
REPORT_TOOL = "media-quality-checker"
DEFAULT_REPORT_NAME = "quality_report.json"


def humanize_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024**2:
        return f"{n / 1024:.1f} KB"
    if n < 1024**3:
        return f"{n / (1024**2):.1f} MB"
    return f"{n / (1024**3):.2f} GB"


def write_report(
    report_path: Path | str,
    *,
    scan_result: ScanResult,
    action_result: ActionResult,
    recursive: bool,
    config: dict[str, Any],
) -> Path:
    summary = {
        "total_scanned": scan_result.total_scanned,
        "valid": scan_result.valid_count,
        "invalid": scan_result.invalid_count,
        "reasons": scan_result.reasons,
    }
    payload = {
        "version": REPORT_VERSION,
        "tool": REPORT_TOOL,
        "source_root": scan_result.source_root,
        "recursive": recursive,
        "enabled_checks": scan_result.enabled_checks,
        "config": config,
        "summary": summary,
        "action": action_result.action,
        "invalid_dir": action_result.invalid_dir,
        "actions": [e.to_dict() for e in action_result.entries],
        "skipped": action_result.skipped,
        "results": scan_result.results,
    }
    out = Path(report_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return out
