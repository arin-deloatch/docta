"""Report generation and output utilities."""

from __future__ import annotations

import json
from pathlib import Path

from ..models.models import DeltaReport


def write_report(report: DeltaReport, output_path: str) -> None:
    """
    Write DeltaReport to JSON file.

    Note: Path validation should be done at CLI layer using validate_output_path()
    before calling this function.

    Args:
        report: DeltaReport to serialize
        output_path: Validated output file path

    Raises:
        OSError: If file cannot be written
    """
    path = Path(output_path)

    # Write atomically using a temporary file
    temp_path = path.with_suffix(".tmp")
    try:
        temp_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        temp_path.replace(path)  # Atomic rename
    except Exception:
        # Clean up temp file on error
        if temp_path.exists():
            temp_path.unlink()
        raise


def summarize_report(report: DeltaReport) -> str:
    """Generate a JSON summary of the delta report."""
    payload = {
        "old_version": report.old_version,
        "new_version": report.new_version,
        "counts": {
            "unchanged": len(report.unchanged),
            "modified": len(report.modified),
            "renamed_candidates": len(report.renamed_candidates),
            "removed": len(report.removed),
            "added": len(report.added),
        },
    }
    return json.dumps(payload, indent=2)
