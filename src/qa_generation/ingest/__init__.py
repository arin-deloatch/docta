"""Data ingestion from semantic diff reports."""

from qa_generation.ingest.diff_report_reader import (
    DiffReportReadError,
    load_report_safe,
    read_diff_report,
)
from qa_generation.ingest.snippet_extractor import (
    extract_snippets,
    extract_snippets_by_topic,
    preview_extraction,
)

__all__ = [
    "read_diff_report",
    "load_report_safe",
    "DiffReportReadError",
    "extract_snippets",
    "extract_snippets_by_topic",
    "preview_extraction",
]
