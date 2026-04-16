"""Convert ExtractedDocument sections to QASourceDocument format."""

from __future__ import annotations

from pathlib import Path

import structlog

from docta.models import DeltaReport
from docta.models.content import ExtractedDocument, Section
from qa_generation.models import AddedDocumentStats, FilterConfig, QASourceDocument

logger = structlog.get_logger(__name__)


def _assemble_section_content(section: Section) -> str:
    """Assemble section content from heading + text blocks + code blocks.

    Format:
        {heading_text}

        {text_block_1}
        {text_block_2}

        {code_block_1}
        {text_block_3}

    Args:
        section: Section from ExtractedDocument

    Returns:
        Assembled content string with heading, text blocks, and code blocks
    """
    parts = []

    # Add heading if present
    if section.heading and section.heading.text:
        parts.append(section.heading.text)

    # Add text blocks
    for text_block in section.text_blocks:
        if text_block.text:
            parts.append(text_block.text)

    # Add code blocks (preserve code as text)
    for code_block in section.code_blocks:
        if code_block.code:
            parts.append(code_block.code)

    return "\n\n".join(parts)


def _build_section_path(section: Section, parent_path: str = "") -> str:
    """Build hierarchical section path from heading structure.

    Example: "Installation > Prerequisites > Hardware Requirements"

    Args:
        section: Section with heading
        parent_path: Parent section path (empty for root sections)

    Returns:
        Hierarchical section path string
    """
    if not section.heading or not section.heading.text:
        return parent_path

    if parent_path:
        return f"{parent_path} > {section.heading.text}"
    return section.heading.text


def _section_to_source_document(
    section: Section,
    topic_slug: str,
    version: str,
    parent_path: str = "",
) -> QASourceDocument | None:
    """Convert a Section to QASourceDocument.

    Args:
        section: Section from ExtractedDocument
        topic_slug: Document topic slug
        version: Version string (e.g., "10")
        parent_path: Hierarchical parent section path

    Returns:
        QASourceDocument or None if section has no content
    """
    # Assemble content
    content = _assemble_section_content(section)

    # Skip if no content
    if not content or not content.strip():
        return None

    # Build location path
    location = _build_section_path(section, parent_path)

    # Create metadata
    metadata = {
        "versions": {
            "added_in": version,
            "new": version,
        },
        "document_content": content,  # Store source content for traceability
    }

    return QASourceDocument(
        content=content,
        topic_slug=topic_slug,
        location=location or None,  # Use None if empty string
        change_type="document_added",
        metadata=metadata,
    )


def _flatten_sections(
    section: Section,
    topic_slug: str,
    version: str,
    parent_path: str = "",
) -> list[QASourceDocument]:
    """Recursively flatten sections into QASourceDocument list.

    Args:
        section: Section to flatten (including subsections)
        topic_slug: Document topic slug
        version: Version string
        parent_path: Hierarchical parent section path

    Returns:
        List of QASourceDocument objects from this section and all subsections
    """
    result = []

    # Convert this section
    source_doc = _section_to_source_document(section, topic_slug, version, parent_path)
    if source_doc:
        result.append(source_doc)

    # Build path for subsections
    current_path = _build_section_path(section, parent_path)

    # Recursively process subsections
    for subsection in section.subsections:
        result.extend(_flatten_sections(subsection, topic_slug, version, current_path))

    return result


def _apply_length_filter(
    source_docs: list[QASourceDocument],
    config: FilterConfig,
    stats: AddedDocumentStats,
) -> list[QASourceDocument]:
    """Apply text length filtering to source documents.

    Args:
        source_docs: List of QASourceDocument to filter
        config: FilterConfig with min/max text length
        stats: Stats object to mutate

    Returns:
        Filtered list of QASourceDocument
    """
    filtered = []

    for doc in source_docs:
        content_length = len(doc.content)

        if content_length < config.min_text_length:
            stats.filtered_by_length += 1
            logger.debug(
                "section_filtered_too_short",
                topic_slug=doc.topic_slug,
                location=doc.location,
                length=content_length,
                min_length=config.min_text_length,
            )
            continue

        if content_length > config.max_text_length:
            stats.filtered_by_length += 1
            logger.debug(
                "section_filtered_too_long",
                topic_slug=doc.topic_slug,
                location=doc.location,
                length=content_length,
                max_length=config.max_text_length,
            )
            continue

        filtered.append(doc)

    return filtered


def _get_topic_slug_from_document(
    extracted_doc: ExtractedDocument,
    delta_report: DeltaReport,
) -> str | None:
    """Extract topic slug from ExtractedDocument by matching source_path.

    Args:
        extracted_doc: ExtractedDocument with source_path
        delta_report: DeltaReport containing added DocumentRecords

    Returns:
        Topic slug if found, None otherwise
    """
    # Match extracted_doc.source_path to doc_record.root / relative_path
    source_path_str = str(Path(extracted_doc.source_path).resolve())

    for doc_record in delta_report.added:
        expected_path = str((Path(doc_record.root) / doc_record.relative_path).resolve())
        if source_path_str == expected_path:
            return doc_record.topic_slug

    # Fallback: try filename matching (last resort)
    source_filename = Path(extracted_doc.source_path).name
    for doc_record in delta_report.added:
        if doc_record.html_filename == source_filename:
            return doc_record.topic_slug

    return None


def convert_added_documents(
    extracted_docs: list[ExtractedDocument],
    delta_report: DeltaReport,
    config: FilterConfig,
    stats: AddedDocumentStats,
) -> list[QASourceDocument]:
    """Convert ExtractedDocument sections to QASourceDocument format.

    Args:
        extracted_docs: List of ExtractedDocument objects
        delta_report: DeltaReport for version info and topic slug mapping
        config: FilterConfig for text length filtering
        stats: Stats object to mutate during processing

    Returns:
        List of QASourceDocument ready for QA generation

    Note:
        This function mutates the stats object to track conversion progress.
        Sections are flattened recursively, and text length filtering is applied.
    """
    if not extracted_docs:
        logger.info("no_extracted_documents_to_convert")
        return []

    logger.info(
        "converting_added_documents",
        total_documents=len(extracted_docs),
        new_version=delta_report.new_version,
    )

    all_source_docs: list[QASourceDocument] = []

    for extracted_doc in extracted_docs:
        # Get topic slug for this document
        topic_slug = _get_topic_slug_from_document(extracted_doc, delta_report)

        if not topic_slug:
            logger.warning(
                "topic_slug_not_found_for_document",
                source_path=extracted_doc.source_path,
            )
            stats.filtered_no_content += 1
            continue

        # Process all sections (flatten recursively)
        for section in extracted_doc.sections:
            section_docs = _flatten_sections(
                section,
                topic_slug,
                delta_report.new_version,
                parent_path="",
            )
            all_source_docs.extend(section_docs)
            stats.total_sections_extracted += len(section_docs)

        logger.debug(
            "document_sections_extracted",
            topic_slug=topic_slug,
            sections=len(extracted_doc.sections),
            source_docs_created=sum(len(_flatten_sections(s, topic_slug, delta_report.new_version)) for s in extracted_doc.sections),
        )

    # Apply text length filtering
    filtered_docs = _apply_length_filter(all_source_docs, config, stats)
    stats.converted_sources = len(filtered_docs)

    logger.info(
        "added_document_conversion_complete",
        total_sections_extracted=stats.total_sections_extracted,
        filtered_by_length=stats.filtered_by_length,
        converted_sources=stats.converted_sources,
        conversion_rate=stats.conversion_rate,
    )

    return filtered_docs
