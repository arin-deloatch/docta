"""Data models for extracted document content."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TextBlock(BaseModel):
    """Represents a block of text content."""

    block_type: Literal["paragraph", "text", "list_item", "table_cell"]
    text: str
    html_snippet: str  # Preserve original HTML
    char_count: int
    word_count: int


class CodeBlock(BaseModel):
    """Represents a code block or inline code."""

    code: str
    language: str | None = None
    is_inline: bool = False
    html_snippet: str
    line_count: int


class ListBlock(BaseModel):
    """Represents a list (ordered or unordered)."""

    list_type: Literal["ul", "ol"]
    items: list[str]  # Plain text of each item
    item_html: list[str]  # HTML of each item (preserves nested structure)
    is_nested: bool = False
    html_snippet: str


class TableBlock(BaseModel):
    """Represents a table with full cell data."""

    headers: list[str] | None = None  # First row if <thead> present
    rows: list[list[str]]  # All data rows as plain text
    row_html: list[str]  # Full HTML of each row
    column_count: int
    row_count: int
    has_header: bool
    html_snippet: str


class Heading(BaseModel):
    """Represents a heading element."""

    text: str
    level: int = Field(ge=1, le=6)
    html_snippet: str
    id_attr: str | None = None  # Anchor ID if present


class ImageBlock(BaseModel):
    """Represents an image."""

    src: str
    alt: str | None = None
    title: str | None = None
    html_snippet: str


class LinkBlock(BaseModel):
    """Represents a hyperlink."""

    text: str
    href: str
    title: str | None = None
    is_external: bool = False
    html_snippet: str


class Section(BaseModel):
    """
    Represents a semantic section of the document.

    A section is typically defined by a heading and contains all content
    until the next heading of the same or higher level.
    """

    heading: Heading | None = None  # None for intro/preamble sections
    text_blocks: list[TextBlock] = Field(default_factory=list)
    code_blocks: list[CodeBlock] = Field(default_factory=list)
    lists: list[ListBlock] = Field(default_factory=list)
    tables: list[TableBlock] = Field(default_factory=list)
    images: list[ImageBlock] = Field(default_factory=list)
    links: list[LinkBlock] = Field(default_factory=list)
    subsections: list[Section] = Field(default_factory=list)

    # Metadata
    level: int = 0  # Section nesting level
    section_id: str | None = None  # Unique identifier for matching
    start_html_index: int = 0  # Position in original HTML

    @property
    def total_text(self) -> str:
        """Get all text content in this section."""
        parts = []
        if self.heading:
            parts.append(self.heading.text)
        parts.extend(block.text for block in self.text_blocks)
        return "\n".join(parts)

    @property
    def total_char_count(self) -> int:
        """Total character count in this section."""
        return sum(block.char_count for block in self.text_blocks)

    @property
    def has_content(self) -> bool:
        """Check if section has any content."""
        return bool(
            self.text_blocks
            or self.code_blocks
            or self.lists
            or self.tables
            or self.images
            or self.subsections
        )


class DocumentMetadata(BaseModel):
    """Document-level metadata."""

    title: str | None = None
    description: str | None = None
    keywords: list[str] = Field(default_factory=list)
    author: str | None = None
    meta_tags: dict[str, str] = Field(default_factory=dict)
    lang: str | None = None


class ExtractedDocument(BaseModel):
    """
    Complete extracted content from an HTML document.

    This preserves ALL content while organizing it semantically
    for efficient diffing.
    """

    metadata: DocumentMetadata
    sections: list[Section]

    # Global aggregates (for quick stats)
    all_headings: list[Heading] = Field(default_factory=list)
    all_code_blocks: list[CodeBlock] = Field(default_factory=list)
    all_tables: list[TableBlock] = Field(default_factory=list)
    all_images: list[ImageBlock] = Field(default_factory=list)
    all_links: list[LinkBlock] = Field(default_factory=list)

    # Full text for similarity comparison
    full_text: str = ""
    total_char_count: int = 0
    total_word_count: int = 0

    # Preserve original HTML reference
    source_path: str

    @property
    def section_count(self) -> int:
        """Total number of sections."""
        return len(self.sections)

    @property
    def heading_structure(self) -> list[tuple[int, str]]:
        """Get document outline as (level, text) pairs."""
        return [(h.level, h.text) for h in self.all_headings]
