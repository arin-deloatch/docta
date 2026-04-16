"""Extract structured content from HTML documents."""

from __future__ import annotations

from pathlib import Path

import structlog
from bs4 import BeautifulSoup, Tag

from docta.models.content import (
    CodeBlock,
    DocumentMetadata,
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
    BLOCK_EXTRACTION_ELEMENTS,
    BLOCK_LEVEL_ELEMENTS,
    CONTAINER_ELEMENTS,
    HEADING_ELEMENTS,
    MAX_SECTION_DEPTH,
    MIN_TEXT_LENGTH,
    STRUCTURED_CONTENT_ELEMENTS,
)
from docta.utils.text_utils import extract_clean_text, truncate_html_snippet

logger = structlog.get_logger(__name__)


def _extract_metadata(soup: BeautifulSoup) -> DocumentMetadata:
    """Extract document metadata."""
    metadata = DocumentMetadata()

    # Title
    if soup.title and soup.title.string:
        metadata.title = soup.title.string.strip()

    # Meta tags
    meta_tags = {}
    for meta in soup.find_all("meta"):
        name = meta.get("name") or meta.get("property")
        content = meta.get("content")
        if name and content:
            name_str = str(name) if not isinstance(name, str) else name
            content_str = str(content) if not isinstance(content, str) else content
            meta_tags[name_str] = content_str

            # Map common fields
            if name_str.lower() in ("description", "og:description"):
                metadata.description = content_str
            elif name_str.lower() in ("keywords",):
                metadata.keywords = [k.strip() for k in content_str.split(",")]
            elif name_str.lower() in ("author",):
                metadata.author = content_str

    metadata.meta_tags = meta_tags

    # Language
    html_tag = soup.find("html")
    if html_tag and isinstance(html_tag, Tag):
        lang_attr = html_tag.get("lang")
        metadata.lang = str(lang_attr) if lang_attr else None

    return metadata


def _extract_text_block(elem: Tag) -> TextBlock | None:
    """Extract a text block from a paragraph or similar element."""
    text = extract_clean_text(elem)
    if not text:
        return None

    return TextBlock(
        block_type="paragraph",
        text=text,
        html_snippet=truncate_html_snippet(str(elem)),
        char_count=len(text),
        word_count=len(text.split()),
    )


def _extract_code_block(elem: Tag) -> CodeBlock:
    """Extract a code block."""
    # For code, preserve exact whitespace (don't use extract_clean_text)
    code = elem.get_text()
    is_inline = elem.name == "code" and elem.parent is not None and elem.parent.name != "pre"

    # Try to detect language from class
    language = None
    classes_attr = elem.get("class")
    if classes_attr:
        classes = classes_attr if isinstance(classes_attr, list) else [classes_attr]
        for cls in classes:
            cls_str = str(cls)
            if cls_str.startswith("language-"):
                language = cls_str.replace("language-", "")
                break
            if cls_str.startswith("lang-"):
                language = cls_str.replace("lang-", "")
                break

    return CodeBlock(
        code=code,
        language=language,
        is_inline=is_inline,
        html_snippet=truncate_html_snippet(str(elem)),
        line_count=code.count("\n") + 1 if code else 0,
    )


def _extract_list(elem: Tag) -> ListBlock:
    """Extract a list with all items."""
    list_type = "ul" if elem.name == "ul" else "ol"  # type: ignore[arg-type]  # Literal typing checked at runtime
    items = []
    item_html = []

    for li in elem.find_all("li", recursive=False):  # Only direct children
        items.append(extract_clean_text(li))
        item_html.append(truncate_html_snippet(str(li)))

    # Check if nested
    is_nested = bool(elem.find_all(["ul", "ol"]))

    return ListBlock(
        list_type=list_type,  # type: ignore[arg-type]  # Literal typing checked at runtime
        items=items,
        item_html=item_html,
        is_nested=is_nested,
        html_snippet=truncate_html_snippet(str(elem)),
    )


def _extract_table(elem: Tag) -> TableBlock:
    """Extract a table with full data."""
    headers = None
    rows = []
    row_html = []

    # Extract headers
    thead = elem.find("thead")
    if thead:
        header_row = thead.find("tr")
        if header_row:
            headers = [extract_clean_text(th) for th in header_row.find_all(["th", "td"])]

    # Extract all rows
    tbody = elem.find("tbody") or elem
    for tr in tbody.find_all("tr"):
        cells = [extract_clean_text(td) for td in tr.find_all(["td", "th"])]
        rows.append(cells)
        row_html.append(truncate_html_snippet(str(tr)))

    column_count = max((len(row) for row in rows), default=0)
    if headers:
        column_count = max(column_count, len(headers))

    return TableBlock(
        headers=headers,
        rows=rows,
        row_html=row_html,
        column_count=column_count,
        row_count=len(rows),
        has_header=headers is not None,
        html_snippet=truncate_html_snippet(str(elem)),
    )


def _extract_heading(elem: Tag) -> Heading:
    """Extract a heading."""
    level = int(elem.name[1])  # h1 -> 1, h2 -> 2, etc.
    text = extract_clean_text(elem)
    id_attr_val = elem.get("id")
    id_attr = str(id_attr_val) if id_attr_val else None

    return Heading(
        text=text,
        level=level,
        html_snippet=truncate_html_snippet(str(elem)),
        id_attr=id_attr,
    )


def _extract_image(elem: Tag) -> ImageBlock:
    """Extract an image."""
    src_val = elem.get("src", "")
    alt_val = elem.get("alt")
    title_val = elem.get("title")

    return ImageBlock(
        src=str(src_val) if src_val else "",
        alt=str(alt_val) if alt_val else None,
        title=str(title_val) if title_val else None,
        html_snippet=truncate_html_snippet(str(elem)),
    )


def _extract_link(elem: Tag) -> LinkBlock:
    """Extract a hyperlink."""
    text = extract_clean_text(elem)
    href_val = elem.get("href", "")
    title_val = elem.get("title")

    href = str(href_val) if href_val else ""
    title = str(title_val) if title_val else None

    # Detect external links
    is_external = href.startswith(("http://", "https://", "//"))

    return LinkBlock(
        text=text,
        href=href,
        title=title,
        is_external=is_external,
        html_snippet=truncate_html_snippet(str(elem)),
    )


def _is_rhel_paragraph(elem: Tag) -> bool:
    """Check if element is RHEL-specific paragraph div."""
    if elem.name != "div":
        return False
    classes = elem.get("class")
    if not classes:
        return False
    class_list = classes if isinstance(classes, list) else [classes]
    return "para" in class_list


def _has_block_level_children(elem: Tag) -> bool:
    """Check if element has block-level children."""
    for child in elem.children:
        if isinstance(child, Tag) and child.name in BLOCK_LEVEL_ELEMENTS:
            return True
    return False


def _should_extract_text_from(elem: Tag) -> bool:
    """
    Determine if we should extract text from this element.
    Only extract from leaf content elements, not wrappers.
    """
    # Direct content elements we always extract
    if elem.name == "p" or _is_rhel_paragraph(elem):
        return True

    # Skip elements with dedicated extractors or special handling
    if elem.name in (HEADING_ELEMENTS | CONTAINER_ELEMENTS | STRUCTURED_CONTENT_ELEMENTS):
        return False

    # For other elements (span, etc.), extract if they have text but no block-level children
    text = elem.get_text(strip=True)
    if text and len(text) > MIN_TEXT_LENGTH:
        return not _has_block_level_children(elem)

    return False


def _is_already_extracted(elem: Tag, body: Tag, extracted_ids: set[int]) -> bool:
    """Check if element or its parent has already been extracted."""
    elem_id = id(elem)

    # Skip if already extracted
    if elem_id in extracted_ids:
        return True

    # Check if this element is inside an already-extracted block element
    for parent in elem.parents:
        if parent == body:
            break
        if id(parent) in extracted_ids and parent.name in BLOCK_EXTRACTION_ELEMENTS:
            return True

    return False


def _process_heading(
    elem: Tag,
    sections: list[Section],
    section_stack: list[Section],
    extracted_ids: set[int],
) -> Section:
    """Process a heading element and create a new section."""
    extracted_ids.add(id(elem))
    heading = _extract_heading(elem)

    # Validate section depth to prevent stack overflow
    if len(section_stack) >= MAX_SECTION_DEPTH:
        raise ValueError(f"Section nesting depth exceeds maximum ({MAX_SECTION_DEPTH}). " "Document structure may be malformed.")

    # Create new section
    new_section = Section(
        heading=heading,
        level=heading.level,
        section_id=heading.id_attr,
    )

    # Determine where to attach based on hierarchy
    while section_stack and section_stack[-1].level >= heading.level:
        section_stack.pop()

    if section_stack:
        # Add as subsection
        section_stack[-1].subsections.append(new_section)
    else:
        # Top-level section
        sections.append(new_section)

    section_stack.append(new_section)
    return new_section


def _process_text_content(elem: Tag, current_section: Section | None, extracted_ids: set[int]) -> None:
    """Process text content element and add to current section."""
    extracted_ids.add(id(elem))
    text_block = _extract_text_block(elem)
    if text_block and current_section:
        current_section.text_blocks.append(text_block)


def _process_code_block(elem: Tag, current_section: Section | None, extracted_ids: set[int]) -> None:
    """Process code block element and add to current section."""
    extracted_ids.add(id(elem))

    if elem.name == "pre":
        # Also mark the inner <code> as extracted
        code_elem = elem.find("code")
        if code_elem:
            extracted_ids.add(id(code_elem))
        code_block = _extract_code_block(code_elem or elem)
    else:
        code_block = _extract_code_block(elem)

    if current_section:
        current_section.code_blocks.append(code_block)


def _process_list(elem: Tag, current_section: Section | None, extracted_ids: set[int]) -> None:
    """Process list element and add to current section."""
    extracted_ids.add(id(elem))

    # Mark all descendants as extracted
    for desc in elem.descendants:
        if isinstance(desc, Tag):
            extracted_ids.add(id(desc))

    list_block = _extract_list(elem)
    if current_section:
        current_section.lists.append(list_block)


def _process_table(elem: Tag, current_section: Section | None, extracted_ids: set[int]) -> None:
    """Process table element and add to current section."""
    extracted_ids.add(id(elem))

    # Mark all descendants as extracted
    for desc in elem.descendants:
        if isinstance(desc, Tag):
            extracted_ids.add(id(desc))

    table_block = _extract_table(elem)
    if current_section:
        current_section.tables.append(table_block)


def _process_image(elem: Tag, current_section: Section | None, extracted_ids: set[int]) -> None:
    """Process image element and add to current section."""
    extracted_ids.add(id(elem))
    image_block = _extract_image(elem)
    if current_section:
        current_section.images.append(image_block)


def _process_link(elem: Tag, current_section: Section | None, extracted_ids: set[int]) -> None:
    """Process link element and add to current section."""
    extracted_ids.add(id(elem))
    link_block = _extract_link(elem)
    if current_section:
        current_section.links.append(link_block)


def _build_sections(body: Tag) -> list[Section]:
    """
    Build hierarchical sections from body content.

    Sections are delimited by headings. Content between headings
    belongs to the section started by the previous heading.

    This approach properly handles nested HTML structures by:
    1. Finding all headings first to establish section boundaries
    2. Walking the tree and assigning content to the current section
    3. Skipping nested content elements to avoid duplicates
    """
    sections: list[Section] = []
    current_section = Section(level=0)  # Preamble/intro
    section_stack = [current_section]
    extracted_ids: set[int] = set()

    # Walk through all elements in document order
    for elem in body.descendants:
        if not isinstance(elem, Tag):
            continue

        # Skip if already extracted
        if _is_already_extracted(elem, body, extracted_ids):
            continue

        # Heading - start new section
        if elem.name in HEADING_ELEMENTS:
            current_section = _process_heading(elem, sections, section_stack, extracted_ids)

        # Text content
        elif elem.name == "p" or _should_extract_text_from(elem):
            _process_text_content(elem, current_section, extracted_ids)

        # Code blocks
        elif elem.name == "pre":
            _process_code_block(elem, current_section, extracted_ids)

        elif elem.name == "code" and elem.parent and elem.parent.name != "pre":
            # Inline code only (not inside <pre>)
            _process_code_block(elem, current_section, extracted_ids)

        # Lists
        elif elem.name in {"ul", "ol"}:
            _process_list(elem, current_section, extracted_ids)

        # Tables
        elif elem.name == "table":
            _process_table(elem, current_section, extracted_ids)

        # Images
        elif elem.name == "img":
            _process_image(elem, current_section, extracted_ids)

        # Links
        elif elem.name == "a":
            _process_link(elem, current_section, extracted_ids)

    # Add preamble if it has content
    if section_stack[0].has_content and not section_stack[0].heading:
        sections.insert(0, section_stack[0])

    return sections


def _collect_all_elements(sections: list[Section]) -> tuple[
    list[Heading],
    list[CodeBlock],
    list[TableBlock],
    list[ImageBlock],
    list[LinkBlock],
]:
    """Recursively collect all elements from sections."""
    all_headings = []
    all_code_blocks = []
    all_tables = []
    all_images = []
    all_links = []

    def recurse(section: Section) -> None:
        if section.heading:
            all_headings.append(section.heading)
        all_code_blocks.extend(section.code_blocks)
        all_tables.extend(section.tables)
        all_images.extend(section.images)
        all_links.extend(section.links)

        for subsection in section.subsections:
            recurse(subsection)

    for section in sections:
        recurse(section)

    return all_headings, all_code_blocks, all_tables, all_images, all_links


def _load_html_file(html_path: Path) -> str:
    """Load HTML content from file with error handling."""
    try:
        return html_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        logger.error("file_not_found", path=str(html_path))
        raise FileNotFoundError(f"HTML file not found: {html_path}") from exc
    except PermissionError as exc:
        logger.error("permission_denied", path=str(html_path))
        raise PermissionError(f"Permission denied reading file: {html_path}") from exc
    except UnicodeDecodeError as e:
        logger.error("unicode_decode_error", path=str(html_path), reason=e.reason)
        raise UnicodeDecodeError(
            e.encoding,
            e.object,
            e.start,
            e.end,
            f"Failed to decode {html_path} as UTF-8: {e.reason}",
        ) from e


def _calculate_full_text_stats(sections: list[Section]) -> tuple[str, int, int]:
    """Calculate full text and statistics from sections."""

    def _collect_section_text(section: Section, parts: list[str]) -> int:
        """Recursively collect text from section and subsections."""
        char_count = 0
        if section.total_text:
            parts.append(section.total_text)
            char_count += section.total_char_count
        for subsection in section.subsections:
            char_count += _collect_section_text(subsection, parts)
        return char_count

    text_parts: list[str] = []
    char_count = sum(_collect_section_text(s, text_parts) for s in sections)  # type: ignore[misc]  # Generator returns int (char count)
    full_text = "\n\n".join(text_parts)
    return full_text, char_count, len(full_text.split())


def extract_document_content(html_path: Path) -> ExtractedDocument:
    """
    Extract all content from an HTML document.

    Args:
        html_path: Path to HTML file

    Returns:
        ExtractedDocument with complete structured content

    Raises:
        FileNotFoundError: If the HTML file does not exist
        PermissionError: If the file cannot be read
        UnicodeDecodeError: If the file encoding is invalid
    """
    logger.debug("extracting_document_content", path=str(html_path))

    html = _load_html_file(html_path)
    soup = BeautifulSoup(html, "lxml")
    metadata = _extract_metadata(soup)

    body = soup.find("body") or soup
    sections = _build_sections(body)

    all_headings, all_code_blocks, all_tables, all_images, all_links = _collect_all_elements(sections)

    full_text, total_char_count, total_word_count = _calculate_full_text_stats(sections)

    logger.debug(
        "document_content_extracted",
        path=str(html_path),
        sections=len(sections),
        headings=len(all_headings),
        code_blocks=len(all_code_blocks),
        tables=len(all_tables),
        images=len(all_images),
        links=len(all_links),
        char_count=total_char_count,
        word_count=total_word_count,
    )

    return ExtractedDocument(
        metadata=metadata,
        sections=sections,
        all_headings=all_headings,
        all_code_blocks=all_code_blocks,
        all_tables=all_tables,
        all_images=all_images,
        all_links=all_links,
        full_text=full_text,
        total_char_count=total_char_count,
        total_word_count=total_word_count,
        source_path=str(html_path),
    )
