"""Extract and process added documents from delta reports."""

from __future__ import annotations

from pathlib import Path

import structlog
from pydantic import ValidationError

from docta.extract.content_extractor import extract_document_content
from docta.models import DeltaReport
from docta.models.content import ExtractedDocument
from qa_generation.models import AddedDocumentStats, FilterConfig
from qa_generation.utils import validate_and_load_json_report

logger = structlog.get_logger(__name__)


class DeltaReportReadError(Exception):
    """Raised when a delta report cannot be read or validated."""


def read_delta_report(report_path: str | Path) -> DeltaReport:
    """Read and validate a delta report from JSON.

    Args:
        report_path: Path to delta_report.json file

    Returns:
        Validated DeltaReport object

    Raises:
        DeltaReportReadError: If file cannot be read, validated, or fails security checks
    """
    report_path = Path(report_path).resolve()

    logger.info("reading_delta_report", path=str(report_path))

    # Validate and load JSON with security checks
    raw_data = validate_and_load_json_report(
        report_path=report_path,
        error_class=DeltaReportReadError,
        log_context="delta_report",
    )

    # Validate against schema
    try:
        report = DeltaReport.model_validate(raw_data)
    except ValidationError as e:
        logger.error(
            "delta_report_validation_failed",
            path=str(report_path),
            error_count=e.error_count(),  # pylint: disable=no-member  # Pydantic ValidationError methods
            errors=e.errors()[:3],  # pylint: disable=no-member  # Log first 3 errors
        )
        raise DeltaReportReadError(
            f"Delta report validation failed with {e.error_count()} error(s). "  # pylint: disable=no-member
            f"First error: {e.errors()[0]['msg']}"  # pylint: disable=no-member
        ) from e

    logger.info(
        "delta_report_loaded_successfully",
        path=str(report_path),
        old_version=report.old_version,
        new_version=report.new_version,
        unchanged=len(report.unchanged),
        modified=len(report.modified),
        renamed_candidates=len(report.renamed_candidates),
        removed=len(report.removed),
        added=len(report.added),
    )

    return report


def extract_added_documents(
    delta_report: DeltaReport,
    config: FilterConfig,  # pylint: disable=unused-argument
    stats: AddedDocumentStats,
    max_documents: int | None = None,
) -> list[ExtractedDocument]:
    """Extract HTML content from added documents.

    Args:
        delta_report: DeltaReport containing added documents
        config: FilterConfig for filtering settings (currently unused but kept for future)
        stats: Stats object to mutate during processing
        max_documents: Optional limit on number of documents to extract (stops early)

    Returns:
        List of ExtractedDocument objects from successfully parsed HTML files

    Note:
        This function mutates the stats object to track extraction progress.
        Documents that fail to parse are skipped with warnings logged.
    """
    stats.total_added_docs = len(delta_report.added)

    if stats.total_added_docs == 0:
        logger.info("no_added_documents_to_process")
        return []

    logger.info(
        "extracting_added_documents",
        total_added_docs=stats.total_added_docs,
        new_version=delta_report.new_version,
    )

    extracted_docs: list[ExtractedDocument] = []

    for doc_record in delta_report.added:
        # Build full path: doc_record.root / relative_path
        doc_path = Path(doc_record.root) / doc_record.relative_path

        # Validate file exists
        if not doc_path.exists():
            logger.warning(
                "added_document_not_found",
                topic_slug=doc_record.topic_slug,
                path=str(doc_path),
            )
            stats.filtered_invalid_html += 1
            continue

        if not doc_path.is_file():
            logger.warning(
                "added_document_not_a_file",
                topic_slug=doc_record.topic_slug,
                path=str(doc_path),
            )
            stats.filtered_invalid_html += 1
            continue

        # Extract content from HTML
        try:
            extracted_doc = extract_document_content(doc_path)
            extracted_docs.append(extracted_doc)
            logger.debug(
                "added_document_extracted",
                topic_slug=doc_record.topic_slug,
                sections=len(extracted_doc.sections),
                char_count=extracted_doc.total_char_count,
            )

            # Early termination if max_documents limit reached
            if max_documents is not None and len(extracted_docs) >= max_documents:
                logger.info(
                    "max_documents_reached",
                    extracted=len(extracted_docs),
                    max_documents=max_documents,
                )
                break
        except (FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
            logger.warning(
                "added_document_extraction_failed",
                topic_slug=doc_record.topic_slug,
                path=str(doc_path),
                error_type=type(e).__name__,
                error=str(e),
            )
            stats.filtered_invalid_html += 1
            continue
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning(
                "added_document_extraction_unexpected_error",
                topic_slug=doc_record.topic_slug,
                path=str(doc_path),
                error_type=type(e).__name__,
                error=str(e),
            )
            stats.filtered_invalid_html += 1
            continue

    logger.info(
        "added_document_extraction_complete",
        extracted=len(extracted_docs),
        filtered_invalid_html=stats.filtered_invalid_html,
    )

    return extracted_docs
