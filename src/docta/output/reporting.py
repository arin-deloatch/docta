"""Report generation and output utilities."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Protocol

import structlog

from docta.models.models import DeltaReport
from docta.models.html_diff import HTMLDiffReport

logger = structlog.get_logger(__name__)


class ReportModel(Protocol):  # pylint: disable=too-few-public-methods
    """Protocol for report models with model_dump_json method."""

    def model_dump_json(self, *, indent: int) -> str:
        """Serialize model to JSON string."""
        ...  # pylint: disable=unnecessary-ellipsis


def _write_report_atomic(report: ReportModel, output_path: str | Path) -> None:
    """
    Write any Pydantic report to JSON file atomically.

    Uses atomic write pattern with temporary file to prevent corruption.

    Args:
        report: Report model to serialize
        output_path: Validated output file path

    Raises:
        OSError: If file cannot be written
    """
    path = Path(output_path)
    logger.debug("writing_report_atomic", path=str(path))

    path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = path.with_suffix(".tmp")
    try:
        temp_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        temp_path.replace(path)  # Atomic rename
        logger.info("report_written", path=str(path))
    except Exception as e:
        logger.error("failed_to_write_report", path=str(path), error=str(e))
        if temp_path.exists():
            temp_path.unlink()
        raise


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
    _write_report_atomic(report, output_path)


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


def write_html_diff_report(report: HTMLDiffReport, output_path: str) -> None:
    """
    Write HTMLDiffReport to JSON file.

    Note: Path validation should be done at CLI layer using validate_output_path()
    before calling this function.

    Args:
        report: HTMLDiffReport to serialize
        output_path: Validated output file path

    Raises:
        OSError: If file cannot be written
    """
    _write_report_atomic(report, output_path)


def summarize_html_diff_report(report: HTMLDiffReport) -> str:
    """Generate a JSON summary of the HTML diff report."""
    # Aggregate change types using Counter
    change_counts = Counter(change.change_type for result in report.results for change in result.changes)

    # Aggregate error types using Counter
    error_counts = Counter(failure.error_type for failure in report.failed_comparisons)

    # Calculate average similarity
    avg_similarity = sum(r.text_similarity for r in report.results) / len(report.results) if report.results else 0.0

    payload = {
        "old_version": report.old_version,
        "new_version": report.new_version,
        "total_compared": report.total_compared,
        "total_with_changes": report.total_with_changes,
        "total_failed": report.total_failed,
        "change_counts": dict(change_counts),
        "error_counts": dict(error_counts),
        "avg_similarity": avg_similarity,
    }
    return json.dumps(payload, indent=2)
