"""Utilities for loading and validating JSON reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from docta.utils.constants import MAX_REPORT_SIZE_BYTES
from docta.utils.security import SecurityError, validate_file_for_reading

logger = structlog.get_logger(__name__)


def validate_and_load_json_report(
    report_path: Path,
    error_class: type[Exception],
    log_context: str,
) -> dict[str, Any]:
    """Validate and load JSON report with security checks.

    Args:
        report_path: Path to JSON report file
        error_class: Exception class to raise on errors
        log_context: Context string for log messages (e.g., 'delta_report', 'diff_report')

    Returns:
        Parsed JSON data as dictionary

    Raises:
        error_class: If validation fails or JSON is invalid
    """
    # Security validation
    try:
        validate_file_for_reading(
            report_path,
            max_size=MAX_REPORT_SIZE_BYTES,
            allowed_extensions={".json"},
        )
    except SecurityError as e:
        logger.error(
            f"{log_context}_security_validation_failed",
            path=str(report_path),
            error=str(e),
        )
        raise error_class(f"Security validation failed: {e}") from e

    # Read and parse JSON
    try:
        with report_path.open("r", encoding="utf-8") as f:
            parsed: Any = json.load(f)
            if not isinstance(parsed, dict):
                raise error_class(f"Invalid JSON root type in report file: expected object, got {type(parsed).__name__}")
            return parsed
    except json.JSONDecodeError as e:
        logger.error(
            f"{log_context}_json_invalid",
            path=str(report_path),
            error=str(e),
            line=e.lineno,
            column=e.colno,
        )
        raise error_class(f"Invalid JSON in report file: {e.msg} at line {e.lineno}, column {e.colno}") from e
