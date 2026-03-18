"""Utility functions and helpers."""

from doc_diff_tracker.utils.cli_helpers import (
    execute_manifest_comparison,
    validate_common_inputs,
    validate_pipeline_params,
)
from doc_diff_tracker.utils.constants import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
    MAX_FILES_TO_PROCESS,
)
from doc_diff_tracker.utils.inventory import build_manifest, iter_html_docs
from doc_diff_tracker.utils.scanner import (
    load_delta_report,
    process_changes,
    scan_and_compare,
    scan_report_for_changes,
)
from doc_diff_tracker.utils.security import (
    SecurityError,
    validate_file_for_reading,
    validate_float_parameter,
    validate_input_directory,
    validate_output_path,
    validate_version_string,
)
from doc_diff_tracker.utils.text_utils import (
    extract_clean_text,
    normalize_whitespace,
    truncate_html_snippet,
)

__all__ = [
    # CLI helpers
    "validate_pipeline_params",
    "validate_common_inputs",
    "execute_manifest_comparison",
    # Constants
    "ALLOWED_EXTENSIONS",
    "MAX_FILE_SIZE_BYTES",
    "MAX_FILES_TO_PROCESS",
    # Inventory
    "build_manifest",
    "iter_html_docs",
    # Scanner
    "load_delta_report",
    "scan_report_for_changes",
    "process_changes",
    "scan_and_compare",
    # Security
    "SecurityError",
    "validate_input_directory",
    "validate_output_path",
    "validate_file_for_reading",
    "validate_float_parameter",
    "validate_version_string",
    # Text utils
    "normalize_whitespace",
    "extract_clean_text",
    "truncate_html_snippet",
]
