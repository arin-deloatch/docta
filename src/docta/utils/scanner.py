"""Report scanning and HTML diff processing utilities."""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from docta.models.models import DeltaReport, MatchRecord
from docta.models.html_diff import (
    HTMLDiffReport,
    HTMLDiffResult,
    FailedComparison,
    ProcessingResult,
)
from docta.compare.semantic_diff import process_match_record_semantic
from docta.utils.constants import MAX_FILE_SIZE_BYTES

logger = structlog.get_logger(__name__)


def load_delta_report(report_path: Path) -> DeltaReport:
    """
    Load a DeltaReport from JSON file.

    Args:
        report_path: Path to the JSON report file

    Returns:
        Parsed DeltaReport object
    """
    with report_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return DeltaReport(**data)


def scan_report_for_changes(
    report: DeltaReport,
    include_modified: bool = True,
    include_renamed: bool = True,
) -> list[MatchRecord]:
    """
    Scan a DeltaReport and extract records to compare.

    Args:
        report: The delta report to scan
        include_modified: Include modified documents
        include_renamed: Include renamed candidates

    Returns:
        List of MatchRecords to process
    """
    records = []

    if include_modified:
        records.extend(report.modified)
        logger.info("found_modified_documents", count=len(report.modified))

    if include_renamed:
        records.extend(report.renamed_candidates)
        logger.info("found_renamed_candidates", count=len(report.renamed_candidates))

    return records


def _validate_file_size(file_path: Path) -> None:
    """
    Validate that file size is within acceptable limits.

    Args:
        file_path: Path to file to validate

    Raises:
        ValueError: If file exceeds size limit
    """
    file_size = file_path.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File size ({file_size} bytes) exceeds maximum ({MAX_FILE_SIZE_BYTES} bytes)")


def _process_single_match(
    record: MatchRecord,
    old_root: Path,
    new_root: Path,
) -> ProcessingResult:
    """
    Process a single match record with centralized error handling.

    Args:
        record: Match record to process
        old_root: Root directory for old version documents
        new_root: Root directory for new version documents

    Returns:
        ProcessingResult with success status and either result or failure
    """
    old_path = old_root / record.old_relative_path
    new_path = new_root / record.new_relative_path

    try:
        # Validate file sizes
        _validate_file_size(old_path)
        _validate_file_size(new_path)

        # Process semantic diff
        result = process_match_record_semantic(record, old_root, new_root)
        return ProcessingResult(success=True, result=result)

    except (
        ValueError,
        FileNotFoundError,
        OSError,
        RuntimeError,
        UnicodeDecodeError,
    ) as e:
        error_type = type(e).__name__
        logger.warning(
            "failed_to_process_match",
            old_path=record.old_relative_path,
            new_path=record.new_relative_path,
            error_type=error_type,
            error_message=str(e),
        )
        return ProcessingResult(
            success=False,
            failure=FailedComparison(
                old_path=str(old_path),
                new_path=str(new_path),
                error_type=error_type,
                error_message=str(e),
            ),
        )


def process_changes(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    records: list[MatchRecord],
    old_root: Path,
    new_root: Path,
    old_version: str,
    new_version: str,
    max_files: int | None = None,
) -> HTMLDiffReport:
    """
    Process a list of MatchRecords and generate HTML diffs using semantic extraction.

    Args:
        records: List of MatchRecords to process
        old_root: Root directory for old version documents
        new_root: Root directory for new version documents
        old_version: Version label for old documents
        new_version: Version label for new documents
        max_files: Maximum number of files to process (None for all)

    Returns:
        HTMLDiffReport with all comparison results and failed comparisons
    """
    results: list[HTMLDiffResult] = []
    failed_comparisons: list[FailedComparison] = []
    records_to_process = records[:max_files] if max_files else records

    logger.info("processing_document_pairs", total=len(records_to_process))

    for idx, record in enumerate(records_to_process, 1):
        processing_result = _process_single_match(record, old_root, new_root)

        if processing_result.success and processing_result.result:
            results.append(processing_result.result)
        elif processing_result.failure:
            failed_comparisons.append(processing_result.failure)

        if idx % 10 == 0:
            logger.info("processing_progress", processed=idx, total=len(records_to_process))

    total_with_changes = sum(1 for r in results if r.changes)

    logger.info(
        "processing_complete",
        compared=len(results),
        with_changes=total_with_changes,
        failed=len(failed_comparisons),
    )

    return HTMLDiffReport(
        old_version=old_version,
        new_version=new_version,
        old_root=str(old_root),
        new_root=str(new_root),
        results=results,
        failed_comparisons=failed_comparisons,
        total_compared=len(results),
        total_with_changes=total_with_changes,
        total_failed=len(failed_comparisons),
    )


def scan_and_compare(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    report_path: Path,
    old_root: Path,
    new_root: Path,
    include_modified: bool = True,
    include_renamed: bool = True,
    max_files: int | None = None,
) -> HTMLDiffReport:
    """
    Load a delta report, scan for changes, and compare HTML documents using semantic extraction.

    Args:
        report_path: Path to the delta report JSON file
        old_root: Root directory for old version documents
        new_root: Root directory for new version documents
        include_modified: Include modified documents
        include_renamed: Include renamed candidates
        max_files: Maximum number of files to process (None for all)

    Returns:
        HTMLDiffReport with all comparison results
    """
    # Load report
    logger.info("loading_delta_report", path=str(report_path))
    report = load_delta_report(report_path)

    # Scan for records to process
    records = scan_report_for_changes(
        report,
        include_modified=include_modified,
        include_renamed=include_renamed,
    )

    # Process comparisons
    return process_changes(
        records,
        old_root,
        new_root,
        old_version=report.old_version,
        new_version=report.new_version,
        max_files=max_files,
    )
