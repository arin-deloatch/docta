"""Read and validate semantic diff reports for QA generation."""

from __future__ import annotations

import json
from pathlib import Path

import structlog
from pydantic import ValidationError

from doc_diff_tracker.models import HTMLDiffReport
from doc_diff_tracker.utils.constants import MAX_REPORT_SIZE_BYTES
from doc_diff_tracker.utils.security import SecurityError, validate_file_for_reading

logger = structlog.get_logger(__name__)


class DiffReportReadError(Exception):
    """Raised when a diff report cannot be read or validated."""

    pass


def read_diff_report(report_path: str | Path) -> HTMLDiffReport:
    """Read and validate a semantic diff report from JSON.

    Args:
        report_path: Path to semantic_diff_report.json file

    Returns:
        Validated HTMLDiffReport object

    Raises:
        DiffReportReadError: If file cannot be read, validated, or fails security checks
    """
    report_path = Path(report_path).resolve()

    logger.info("reading_diff_report", path=str(report_path))

    # Security validation: check file exists, is regular file, size limits, extension
    try:
        validate_file_for_reading(
            report_path,
            max_size=MAX_REPORT_SIZE_BYTES,
            allowed_extensions={".json"},
        )
    except SecurityError as e:
        logger.error("report_security_validation_failed", path=str(report_path), error=str(e))
        raise DiffReportReadError(f"Security validation failed: {e}") from e

    # Read JSON
    try:
        with report_path.open("r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(
            "report_json_invalid",
            path=str(report_path),
            error=str(e),
            line=e.lineno,
            column=e.colno,
        )
        raise DiffReportReadError(
            f"Invalid JSON in report file: {e.msg} at line {e.lineno}, column {e.colno}"
        ) from e
    except OSError as e:
        logger.error("report_read_failed", path=str(report_path), error=str(e))
        raise DiffReportReadError(f"Failed to read report file: {e}") from e

    # Validate against schema
    try:
        report = HTMLDiffReport.model_validate(raw_data)
    except ValidationError as e:
        logger.error(
            "report_validation_failed",
            path=str(report_path),
            error_count=e.error_count(),
            errors=e.errors()[:3],  # Log first 3 errors
        )
        raise DiffReportReadError(
            f"Report validation failed with {e.error_count()} error(s). "
            f"First error: {e.errors()[0]['msg']}"
        ) from e

    logger.info(
        "report_loaded_successfully",
        path=str(report_path),
        old_version=report.old_version,
        new_version=report.new_version,
        total_results=len(report.results),
        total_compared=report.total_compared,
        total_with_changes=report.total_with_changes,
    )

    return report


def load_report_safe(report_path: str | Path) -> HTMLDiffReport | None:
    """Safely load a diff report, returning None on error.

    This is a wrapper around read_diff_report that catches all errors
    (including security validation failures) and returns None instead of
    raising. Useful for optional report loading where you want to continue
    without a report.

    Note: All exceptions from read_diff_report() (including wrapped
    SecurityError) are caught and logged as warnings.

    Args:
        report_path: Path to semantic_diff_report.json file

    Returns:
        Validated HTMLDiffReport object, or None if loading failed
    """
    try:
        return read_diff_report(report_path)
    except DiffReportReadError as e:
        logger.warning("report_load_failed_safely", path=str(report_path), error=str(e))
        return None
