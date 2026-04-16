"""Block-level semantic diffing for extracted documents."""

from __future__ import annotations

from typing import Literal

import structlog
from pydantic import BaseModel
from rapidfuzz import fuzz

from docta.models.content import (
    CodeBlock,
    ExtractedDocument,
    Heading,
    ImageBlock,
    LinkBlock,
    ListBlock,
    Section,
    TableBlock,
    TextBlock,
)
from docta.utils.constants import (
    BlockChangeType,
    MAX_CONTENT_PREVIEW_LENGTH,
    MAX_PREVIEW_BLOCKS,
    SECTION_MATCH_THRESHOLD,
)

logger = structlog.get_logger(__name__)


class BlockChange(BaseModel):
    """Represents a change at the block level."""

    change_type: BlockChangeType
    description: str
    section_path: str | None = None  # e.g., "Installation > Requirements"
    old_content: str | None = None
    new_content: str | None = None
    old_html: str | None = None
    new_html: str | None = None
    similarity: float | None = None  # 0-100 for modified blocks


class SectionMatch(BaseModel):
    """Matched section pair with comparison results."""

    old_section: Section | None = None
    new_section: Section | None = None
    match_type: Literal["exact", "modified", "added", "removed"]
    section_path: str
    changes: list[BlockChange]
    similarity: float  # 0-100


def _get_section_path(section: Section, parent_path: str = "") -> str:
    """Get hierarchical path for a section."""
    if section.heading:
        current = section.heading.text
    else:
        current = "(preamble)"

    if parent_path:
        return f"{parent_path} > {current}"
    return current


def _build_section_map(sections: list[Section]) -> dict[str, list[Section]]:
    """
    Build a map of sections grouped by heading text and level.

    Handles duplicate headings by storing them in a list.

    Args:
        sections: List of sections to map

    Returns:
        Dictionary mapping (heading_text, level) to list of sections
    """
    section_map: dict[str, list[Section]] = {}

    for i, section in enumerate(sections):
        if section.heading:
            key = f"{section.heading.text}|L{section.level}"
        else:
            key = f"(preamble)|L{section.level}|#{i}"

        if key not in section_map:
            section_map[key] = []
        section_map[key].append(section)

    return section_map


def _find_matching_section(  # pylint: disable=too-many-branches
    new_section: Section,
    old_sections_map: dict[str, list[Section]],
    old_matched: set[int],
) -> tuple[str | None, Section | None]:
    """
    Find the best matching section from old sections using fuzzy matching.

    First tries exact match by key, then falls back to fuzzy matching if threshold met.

    Args:
        new_section: Section to match
        old_sections_map: Map of old sections
        old_matched: Set of already matched section IDs

    Returns:
        Tuple of (matched_key, matched_section) or (None, None) if no match
    """
    if not new_section.heading:
        preamble_key = f"(preamble)|L{new_section.level}|#0"
        if preamble_key in old_sections_map:
            old_sections = old_sections_map[preamble_key]
            for section in old_sections:
                if id(section) not in old_matched:
                    return preamble_key, section
        return None, None

    # Try exact match first
    new_key = f"{new_section.heading.text}|L{new_section.level}"
    if new_key in old_sections_map:
        old_sections = old_sections_map[new_key]
        for section in old_sections:
            if id(section) not in old_matched:
                return new_key, section

    # Fuzzy match: find best match among unmatched sections at same level
    best_match_key = None
    best_match_section = None
    best_similarity = 0.0

    for key, old_sections in old_sections_map.items():
        # Only compare sections at same level
        if not key.startswith("(preamble)") and new_section.level > 0:
            key_level = int(key.split("|L")[1].split("|")[0])
            if key_level != new_section.level:
                continue

        for old_section in old_sections:
            if id(old_section) in old_matched or not old_section.heading:
                continue

            # Calculate fuzzy similarity
            similarity = fuzz.ratio(new_section.heading.text, old_section.heading.text)

            if similarity > best_similarity:
                best_similarity = similarity
                best_match_key = key
                best_match_section = old_section

    # Only return if similarity meets threshold
    if best_similarity >= SECTION_MATCH_THRESHOLD:
        return best_match_key, best_match_section

    return None, None


def truncate_content(content: str, max_length: int = MAX_CONTENT_PREVIEW_LENGTH) -> str:
    """
    Truncate content to a maximum length.

    Args:
        content: Content to truncate
        max_length: Maximum length (default: MAX_CONTENT_PREVIEW_LENGTH)

    Returns:
        Truncated content with ellipsis if needed
    """
    if len(content) <= max_length:
        return content
    return content[:max_length] + "..."


def _create_count_change(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    old_count: int,
    new_count: int,
    added_type: BlockChangeType,
    removed_type: BlockChangeType,
    item_name: str,
    section_path: str,
    new_content: str | None = None,
    old_content: str | None = None,
    new_html: str | None = None,
    old_html: str | None = None,
) -> list[BlockChange]:
    """
    Create block changes based on count differences.

    Args:
        old_count: Number of items in old version
        new_count: Number of items in new version
        added_type: Change type for additions
        removed_type: Change type for removals
        item_name: Name of the item type (e.g., "code block", "table")
        section_path: Section path for the change
        new_content: Optional new content preview
        old_content: Optional old content preview
        new_html: Optional new HTML snippet
        old_html: Optional old HTML snippet

    Returns:
        List of BlockChange (empty if counts are equal, single change otherwise)
    """
    if old_count == new_count:
        return []

    if new_count > old_count:
        return [
            BlockChange(
                change_type=added_type,
                description=f"Added {new_count - old_count} {item_name}(s)",
                section_path=section_path,
                new_content=new_content,
                new_html=new_html,
            )
        ]

    return [
        BlockChange(
            change_type=removed_type,
            description=f"Removed {old_count - new_count} {item_name}(s)",
            section_path=section_path,
            old_content=old_content,
            old_html=old_html,
        )
    ]


def _compare_headings(old: Heading, new: Heading, section_path: str) -> list[BlockChange]:
    """
    Compare two headings for text and level changes.

    Args:
        old: Old heading
        new: New heading
        section_path: Hierarchical path to the section

    Returns:
        List of BlockChange for detected differences
    """
    changes: list[BlockChange] = []

    if old.text != new.text:
        changes.append(
            BlockChange(
                change_type="heading_changed",
                description="Heading text changed",
                section_path=section_path,
                old_content=old.text,
                new_content=new.text,
                old_html=old.html_snippet,
                new_html=new.html_snippet,
            )
        )

    if old.level != new.level:
        changes.append(
            BlockChange(
                change_type="heading_changed",
                description=f"Heading level changed: h{old.level} → h{new.level}",
                section_path=section_path,
            )
        )

    return changes


def _compare_text_blocks(old_blocks: list[TextBlock], new_blocks: list[TextBlock], section_path: str) -> list[BlockChange]:
    """
    Compare text blocks within a section.

    Detects additions, removals, and modifications based on text content.
    Calculates similarity for modified blocks.

    Args:
        old_blocks: Text blocks from old version
        new_blocks: Text blocks from new version
        section_path: Hierarchical path to the section

    Returns:
        List of BlockChange for detected differences
    """
    changes: list[BlockChange] = []

    old_text = "\n".join(b.text for b in old_blocks)
    new_text = "\n".join(b.text for b in new_blocks)

    if old_text == new_text:
        return changes

    # Calculate similarity using rapidfuzz (faster than difflib)
    similarity = fuzz.ratio(old_text, new_text)

    old_count = len(old_blocks)
    new_count = len(new_blocks)

    if old_count == 0 and new_count > 0:
        changes.append(
            BlockChange(
                change_type="text_added",
                description=f"Added {new_count} text block(s)",
                section_path=section_path,
                new_content=new_text,
                new_html="\n".join(b.html_snippet for b in new_blocks[:MAX_PREVIEW_BLOCKS]),
            )
        )
    elif old_count > 0 and new_count == 0:
        changes.append(
            BlockChange(
                change_type="text_removed",
                description=f"Removed {old_count} text block(s)",
                section_path=section_path,
                old_content=old_text,
                old_html="\n".join(b.html_snippet for b in old_blocks[:MAX_PREVIEW_BLOCKS]),
            )
        )
    else:
        # Modified
        char_diff = sum(b.char_count for b in new_blocks) - sum(b.char_count for b in old_blocks)
        changes.append(
            BlockChange(
                change_type="text_modified",
                description=f"Text modified ({char_diff:+d} chars, {similarity:.1f}% similar)",
                section_path=section_path,
                old_content=old_text,
                new_content=new_text,
                old_html="\n".join(b.html_snippet for b in old_blocks[:MAX_PREVIEW_BLOCKS]),
                new_html="\n".join(b.html_snippet for b in new_blocks[:MAX_PREVIEW_BLOCKS]),
                similarity=similarity,
            )
        )

    return changes


def _compare_code_blocks(old_blocks: list[CodeBlock], new_blocks: list[CodeBlock], section_path: str) -> list[BlockChange]:
    """
    Compare code blocks within a section.

    Detects count changes and content modifications.
    Calculates similarity for modified code blocks.

    Args:
        old_blocks: Code blocks from old version
        new_blocks: Code blocks from new version
        section_path: Hierarchical path to the section

    Returns:
        List of BlockChange for detected differences
    """
    changes: list[BlockChange] = []

    old_count = len(old_blocks)
    new_count = len(new_blocks)

    # Handle count differences
    if old_count != new_count:
        changes.extend(
            _create_count_change(
                old_count=old_count,
                new_count=new_count,
                added_type="code_added",
                removed_type="code_removed",
                item_name="code block",
                section_path=section_path,
                new_content=(truncate_content(new_blocks[-1].code) if new_blocks else None),
                new_html=new_blocks[-1].html_snippet if new_blocks else None,
                old_content=(truncate_content(old_blocks[-1].code) if old_blocks else None),
                old_html=old_blocks[-1].html_snippet if old_blocks else None,
            )
        )

    # Compare content of matching blocks
    for i in range(min(old_count, new_count)):
        old_code = old_blocks[i].code
        new_code = new_blocks[i].code

        if old_code != new_code:
            # Use rapidfuzz for faster similarity calculation
            similarity = fuzz.ratio(old_code, new_code)

            changes.append(
                BlockChange(
                    change_type="code_modified",
                    description=f"Code block {i+1} modified ({similarity:.1f}% similar)",
                    section_path=section_path,
                    old_content=truncate_content(old_code),
                    new_content=truncate_content(new_code),
                    old_html=old_blocks[i].html_snippet,
                    new_html=new_blocks[i].html_snippet,
                    similarity=similarity,
                )
            )

    return changes


def _compare_tables(old_tables: list[TableBlock], new_tables: list[TableBlock], section_path: str) -> list[BlockChange]:
    """
    Compare tables within a section.

    Detects count changes, structure changes (rows/columns), and data modifications.

    Args:
        old_tables: Tables from old version
        new_tables: Tables from new version
        section_path: Hierarchical path to the section

    Returns:
        List of BlockChange for detected differences
    """
    changes: list[BlockChange] = []

    old_count = len(old_tables)
    new_count = len(new_tables)

    # Handle count differences
    changes.extend(
        _create_count_change(
            old_count=old_count,
            new_count=new_count,
            added_type="table_added",
            removed_type="table_removed",
            item_name="table",
            section_path=section_path,
        )
    )

    # Compare table structure
    for i in range(min(old_count, new_count)):
        old_table = old_tables[i]
        new_table = new_tables[i]

        if old_table.row_count != new_table.row_count or old_table.column_count != new_table.column_count:
            old_dims = f"{old_table.row_count}×{old_table.column_count}"
            new_dims = f"{new_table.row_count}×{new_table.column_count}"
            changes.append(
                BlockChange(
                    change_type="table_modified",
                    description=f"Table {i+1} structure changed: {old_dims} → {new_dims}",
                    section_path=section_path,
                )
            )
        elif old_table.rows != new_table.rows:
            changes.append(
                BlockChange(
                    change_type="table_modified",
                    description=f"Table {i+1} data modified",
                    section_path=section_path,
                    old_html=old_table.html_snippet,
                    new_html=new_table.html_snippet,
                )
            )

    return changes


def _compare_lists(old_lists: list[ListBlock], new_lists: list[ListBlock], section_path: str) -> list[BlockChange]:
    """Compare lists."""
    changes = []

    old_count = len(old_lists)
    new_count = len(new_lists)

    # Handle count differences
    changes.extend(
        _create_count_change(
            old_count=old_count,
            new_count=new_count,
            added_type="list_added",
            removed_type="list_removed",
            item_name="list",
            section_path=section_path,
        )
    )

    # Compare list items
    for i in range(min(old_count, new_count)):
        old_list = old_lists[i]
        new_list = new_lists[i]

        if old_list.items != new_list.items:
            old_item_count = len(old_list.items)
            new_item_count = len(new_list.items)

            changes.append(
                BlockChange(
                    change_type="list_modified",
                    description=f"List {i+1} modified: {old_item_count} → {new_item_count} items",
                    section_path=section_path,
                    old_html=old_list.html_snippet,
                    new_html=new_list.html_snippet,
                )
            )

    return changes


def _compare_images(old_images: list[ImageBlock], new_images: list[ImageBlock], section_path: str) -> list[BlockChange]:
    """Compare images."""
    changes = []

    old_count = len(old_images)
    new_count = len(new_images)

    # Handle count differences
    changes.extend(
        _create_count_change(
            old_count=old_count,
            new_count=new_count,
            added_type="image_added",
            removed_type="image_removed",
            item_name="image",
            section_path=section_path,
        )
    )

    # Compare image sources
    for i in range(min(old_count, new_count)):
        if old_images[i].src != new_images[i].src:
            changes.append(
                BlockChange(
                    change_type="image_modified",
                    description=f"Image {i+1} source changed",
                    section_path=section_path,
                    old_content=old_images[i].src,
                    new_content=new_images[i].src,
                )
            )

    return changes


def _compare_links(old_links: list[LinkBlock], new_links: list[LinkBlock], section_path: str) -> list[BlockChange]:
    """Compare links."""
    changes = []

    old_count = len(old_links)
    new_count = len(new_links)

    # Handle count differences
    changes.extend(
        _create_count_change(
            old_count=old_count,
            new_count=new_count,
            added_type="link_added",
            removed_type="link_removed",
            item_name="link",
            section_path=section_path,
        )
    )

    return changes


def _compare_sections(old_section: Section, new_section: Section, parent_path: str = "") -> list[BlockChange]:
    """
    Compare two sections recursively.

    Compares all content types (headings, text, code, tables, lists, images, links)
    and recursively processes subsections. Handles duplicate headings correctly.

    Args:
        old_section: Section from old version
        new_section: Section from new version
        parent_path: Hierarchical path to parent section (empty for top-level)

    Returns:
        List of all BlockChange detected in this section and subsections
    """
    changes = []
    section_path = _get_section_path(new_section, parent_path)

    # Compare headings
    if old_section.heading and new_section.heading:
        changes.extend(_compare_headings(old_section.heading, new_section.heading, section_path))

    # Compare text content
    changes.extend(_compare_text_blocks(old_section.text_blocks, new_section.text_blocks, section_path))

    # Compare code blocks
    changes.extend(_compare_code_blocks(old_section.code_blocks, new_section.code_blocks, section_path))

    # Compare tables
    changes.extend(_compare_tables(old_section.tables, new_section.tables, section_path))

    # Compare lists
    changes.extend(_compare_lists(old_section.lists, new_section.lists, section_path))

    # Compare images
    changes.extend(_compare_images(old_section.images, new_section.images, section_path))

    # Compare links
    changes.extend(_compare_links(old_section.links, new_section.links, section_path))

    # Recursively compare subsections with fuzzy matching
    old_subsections_map = _build_section_map(old_section.subsections)

    # Track which sections have been matched
    old_matched: set[int] = set()

    # Find matching subsections using fuzzy matching
    for new_subsection in new_section.subsections:
        matched_old = _find_matching_section(new_subsection, old_subsections_map, old_matched)[1]

        if matched_old:
            # Found a match - compare them
            old_matched.add(id(matched_old))
            changes.extend(_compare_sections(matched_old, new_subsection, section_path))
        else:
            # No match - this is a new section
            subsection_path = _get_section_path(new_subsection, section_path)
            changes.append(
                BlockChange(
                    change_type="section_added",
                    description="Section added",
                    section_path=subsection_path,
                )
            )

    # Find removed subsections (not matched above)
    for old_subsections in old_subsections_map.values():
        for old_subsection in old_subsections:
            if id(old_subsection) not in old_matched:
                subsection_path = _get_section_path(old_subsection, section_path)
                changes.append(
                    BlockChange(
                        change_type="section_removed",
                        description="Section removed",
                        section_path=subsection_path,
                    )
                )

    return changes


def compare_documents(old_doc: ExtractedDocument, new_doc: ExtractedDocument) -> list[BlockChange]:
    """
    Compare two extracted documents at the block level.

    Args:
        old_doc: Old document
        new_doc: New document

    Returns:
        List of all changes detected
    """
    logger.debug(
        "comparing_documents_block_level",
        old_sections=len(old_doc.sections),
        new_sections=len(new_doc.sections),
    )

    changes = []

    # Compare metadata
    if old_doc.metadata.title != new_doc.metadata.title:
        changes.append(
            BlockChange(
                change_type="metadata_changed",
                description="Document title changed",
                old_content=old_doc.metadata.title,
                new_content=new_doc.metadata.title,
            )
        )

    # Map sections by heading text and level, using fuzzy matching
    old_sections_map = _build_section_map(old_doc.sections)

    # Track which sections have been matched
    old_matched: set[int] = set()

    # Find matching sections using fuzzy matching
    for new_section in new_doc.sections:
        matched_old = _find_matching_section(new_section, old_sections_map, old_matched)[1]

        if matched_old:
            # Found a match - compare them
            old_matched.add(id(matched_old))
            changes.extend(_compare_sections(matched_old, new_section))
        else:
            # No match - this is a new section
            section_path = _get_section_path(new_section)
            changes.append(
                BlockChange(
                    change_type="section_added",
                    description="Section added",
                    section_path=section_path,
                )
            )

    # Find removed sections (not matched above)
    for old_sections in old_sections_map.values():
        for old_section in old_sections:
            if id(old_section) not in old_matched:
                section_path = _get_section_path(old_section)
                changes.append(
                    BlockChange(
                        change_type="section_removed",
                        description="Section removed",
                        section_path=section_path,
                    )
                )

    logger.debug("block_level_comparison_complete", changes=len(changes))
    return changes
