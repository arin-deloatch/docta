"""Semantic HTML comparison using content extraction."""

from __future__ import annotations

from pathlib import Path

import structlog
from rapidfuzz import fuzz

from docta.extract.block_differ import (
    BlockChange,
    compare_documents,
    truncate_content,
)
from docta.extract.content_extractor import extract_document_content
from docta.models.html_diff import HTMLChange, HTMLDiffResult
from docta.models.models import MatchRecord
from docta.utils.constants import STRUCTURAL_CHANGE_TYPES, TYPE_MAPPING

logger = structlog.get_logger(__name__)


def _block_change_to_html_change(block_change: BlockChange) -> HTMLChange:
    """Convert a BlockChange to an HTMLChange."""
    change_type = TYPE_MAPPING.get(block_change.change_type, "text_change")

    # Use description as-is, section_path is stored in location field
    description = block_change.description

    # HTML snippets - prefer HTML but fall back to plain text
    old_html_snippet = block_change.old_html or block_change.old_content
    new_html_snippet = block_change.new_html or block_change.new_content

    # Plain text content
    old_text = block_change.old_content
    new_text = block_change.new_content

    return HTMLChange(
        change_type=change_type,
        description=description,
        old_html_snippet=(truncate_content(old_html_snippet) if old_html_snippet else None),
        new_html_snippet=(truncate_content(new_html_snippet) if new_html_snippet else None),
        old_text=old_text,
        new_text=new_text,
        location=block_change.section_path,
    )


def compare_html_documents_semantic(
    old_path: Path,
    new_path: Path,
    old_topic_slug: str,
    new_topic_slug: str,
    relationship: str,
) -> HTMLDiffResult:
    """
    Compare two HTML documents using semantic extraction and block-level diffing.

    This approach:
    1. Extracts all content from both documents (preserving everything)
    2. Compares at the block/section level (headings, paragraphs, code, tables)
    3. Ignores cosmetic HTML changes (class names, wrapper divs)
    4. Reports changes semantically ("Installation section modified")

    Args:
        old_path: Path to the old HTML document
        new_path: Path to the new HTML document
        old_topic_slug: Topic slug for old document
        new_topic_slug: Topic slug for new document
        relationship: Relationship type (modified, renamed_candidate, etc.)

    Returns:
        HTMLDiffResult with semantic changes
    """
    logger.debug(
        "comparing_documents",
        old_path=str(old_path),
        new_path=str(new_path),
        relationship=relationship,
    )

    # Extract content from both documents
    old_doc = extract_document_content(old_path)
    new_doc = extract_document_content(new_path)

    # Calculate text similarity using extracted full text (rapidfuzz is faster than difflib)
    text_similarity = fuzz.ratio(old_doc.full_text, new_doc.full_text)

    # Perform block-level comparison
    block_changes = compare_documents(old_doc, new_doc)

    # Convert block changes to HTML changes
    html_changes = [_block_change_to_html_change(bc) for bc in block_changes]

    # Determine if there are structural changes
    has_structural_changes = any(bc.change_type in STRUCTURAL_CHANGE_TYPES for bc in block_changes)

    logger.debug(
        "documents_compared",
        changes=len(html_changes),
        text_similarity=text_similarity,
        has_structural_changes=has_structural_changes,
    )

    return HTMLDiffResult(
        old_path=str(old_path),
        new_path=str(new_path),
        old_topic_slug=old_topic_slug,
        new_topic_slug=new_topic_slug,
        relationship=relationship,
        changes=html_changes,
        text_similarity=text_similarity,
        has_structural_changes=has_structural_changes,
    )


def process_match_record_semantic(
    match: MatchRecord,
    old_root: Path,
    new_root: Path,
) -> HTMLDiffResult:
    """
    Process a MatchRecord using semantic comparison.

    Args:
        match: MatchRecord from the delta report
        old_root: Root directory for old version
        new_root: Root directory for new version

    Returns:
        HTMLDiffResult with semantic changes
    """
    old_path = old_root / match.old_relative_path
    new_path = new_root / match.new_relative_path

    return compare_html_documents_semantic(
        old_path,
        new_path,
        old_topic_slug=match.old_topic_slug,
        new_topic_slug=match.new_topic_slug,
        relationship=match.relationship,
    )
