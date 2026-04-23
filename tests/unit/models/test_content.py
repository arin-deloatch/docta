"""Unit tests for docta.models.content module."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from docta.models.content import (
    TextBlock,
    CodeBlock,
    ListBlock,
    TableBlock,
    Heading,
    ImageBlock,
    LinkBlock,
    Section,
    DocumentMetadata,
    ExtractedDocument,
)


class TestTextBlock:
    """Tests for TextBlock model."""

    @pytest.fixture
    def sample_text_block_data(self) -> dict:
        """Fixture providing sample text block data."""
        return {
            "block_type": "paragraph",
            "text": "This is a sample paragraph.",
            "html_snippet": "<p>This is a sample paragraph.</p>",
            "char_count": 27,
            "word_count": 5,
        }

    def test_valid_text_block(self, sample_text_block_data: dict) -> None:
        """Test creating valid TextBlock."""
        block = TextBlock(**sample_text_block_data)
        assert block.block_type == "paragraph"
        assert block.text == "This is a sample paragraph."
        assert block.char_count == 27
        assert block.word_count == 5

    @pytest.mark.parametrize(
        "block_type",
        ["paragraph", "text", "list_item", "table_cell"],
    )
    def test_valid_block_types(self, sample_text_block_data: dict, block_type: str) -> None:
        """Test all valid block types."""
        data = sample_text_block_data.copy()
        data["block_type"] = block_type
        block = TextBlock(**data)
        assert block.block_type == block_type

    def test_invalid_block_type(self, sample_text_block_data: dict) -> None:
        """Test that invalid block types raise ValidationError."""
        data = sample_text_block_data.copy()
        data["block_type"] = "invalid_type"
        with pytest.raises(ValidationError):
            TextBlock(**data)

    def test_empty_text_allowed(self, sample_text_block_data: dict) -> None:
        """Test that empty text is allowed."""
        data = sample_text_block_data.copy()
        data["text"] = ""
        data["char_count"] = 0
        data["word_count"] = 0
        block = TextBlock(**data)
        assert block.text == ""


class TestCodeBlock:
    """Tests for CodeBlock model."""

    @pytest.fixture
    def sample_code_block_data(self) -> dict:
        """Fixture providing sample code block data."""
        return {
            "code": "def hello():\n    print('world')",
            "language": "python",
            "is_inline": False,
            "html_snippet": "<pre><code>def hello():\n    print('world')</code></pre>",
            "line_count": 2,
        }

    def test_valid_code_block(self, sample_code_block_data: dict) -> None:
        """Test creating valid CodeBlock."""
        block = CodeBlock(**sample_code_block_data)
        assert block.code == "def hello():\n    print('world')"
        assert block.language == "python"
        assert block.is_inline is False
        assert block.line_count == 2

    def test_inline_code(self, sample_code_block_data: dict) -> None:
        """Test inline code block."""
        data = sample_code_block_data.copy()
        data["is_inline"] = True
        data["line_count"] = 1
        block = CodeBlock(**data)
        assert block.is_inline is True

    def test_code_without_language(self, sample_code_block_data: dict) -> None:
        """Test code block without language specification."""
        data = sample_code_block_data.copy()
        data["language"] = None
        block = CodeBlock(**data)
        assert block.language is None

    @pytest.mark.parametrize(
        ("language", "expected"),
        [
            ("python", "python"),
            ("javascript", "javascript"),
            ("bash", "bash"),
            (None, None),
        ],
    )
    def test_various_languages(self, sample_code_block_data: dict, language: str | None, expected: str | None) -> None:
        """Test code blocks with various languages."""
        data = sample_code_block_data.copy()
        data["language"] = language
        block = CodeBlock(**data)
        assert block.language == expected


class TestListBlock:
    """Tests for ListBlock model."""

    @pytest.fixture
    def sample_list_block_data(self) -> dict:
        """Fixture providing sample list block data."""
        return {
            "list_type": "ul",
            "items": ["First item", "Second item", "Third item"],
            "item_html": ["<li>First item</li>", "<li>Second item</li>", "<li>Third item</li>"],
            "is_nested": False,
            "html_snippet": "<ul><li>First item</li><li>Second item</li><li>Third item</li></ul>",
        }

    def test_valid_list_block(self, sample_list_block_data: dict) -> None:
        """Test creating valid ListBlock."""
        block = ListBlock(**sample_list_block_data)
        assert block.list_type == "ul"
        assert len(block.items) == 3
        assert block.is_nested is False

    @pytest.mark.parametrize(
        "list_type",
        ["ul", "ol"],
    )
    def test_valid_list_types(self, sample_list_block_data: dict, list_type: str) -> None:
        """Test both valid list types."""
        data = sample_list_block_data.copy()
        data["list_type"] = list_type
        block = ListBlock(**data)
        assert block.list_type == list_type

    def test_invalid_list_type(self, sample_list_block_data: dict) -> None:
        """Test that invalid list types raise ValidationError."""
        data = sample_list_block_data.copy()
        data["list_type"] = "dl"
        with pytest.raises(ValidationError):
            ListBlock(**data)

    def test_nested_list(self, sample_list_block_data: dict) -> None:
        """Test nested list block."""
        data = sample_list_block_data.copy()
        data["is_nested"] = True
        block = ListBlock(**data)
        assert block.is_nested is True

    def test_empty_list(self, sample_list_block_data: dict) -> None:
        """Test list block with no items."""
        data = sample_list_block_data.copy()
        data["items"] = []
        data["item_html"] = []
        block = ListBlock(**data)
        assert len(block.items) == 0


class TestTableBlock:
    """Tests for TableBlock model."""

    @pytest.fixture
    def sample_table_block_data(self) -> dict:
        """Fixture providing sample table block data."""
        return {
            "headers": ["Name", "Age", "City"],
            "rows": [["Alice", "30", "NYC"], ["Bob", "25", "LA"]],
            "row_html": ["<tr><td>Alice</td><td>30</td><td>NYC</td></tr>", "<tr><td>Bob</td><td>25</td><td>LA</td></tr>"],
            "column_count": 3,
            "row_count": 2,
            "has_header": True,
            "html_snippet": "<table>...</table>",
        }

    def test_valid_table_block(self, sample_table_block_data: dict) -> None:
        """Test creating valid TableBlock."""
        block = TableBlock(**sample_table_block_data)
        assert block.column_count == 3
        assert block.row_count == 2
        assert block.has_header is True
        assert block.headers is not None
        assert len(block.headers) == 3

    def test_table_without_headers(self, sample_table_block_data: dict) -> None:
        """Test table block without headers."""
        data = sample_table_block_data.copy()
        data["headers"] = None
        data["has_header"] = False
        block = TableBlock(**data)
        assert block.headers is None
        assert block.has_header is False

    def test_empty_table(self, sample_table_block_data: dict) -> None:
        """Test table block with no rows."""
        data = sample_table_block_data.copy()
        data["rows"] = []
        data["row_html"] = []
        data["row_count"] = 0
        block = TableBlock(**data)
        assert len(block.rows) == 0
        assert block.row_count == 0


class TestHeading:
    """Tests for Heading model."""

    @pytest.fixture
    def sample_heading_data(self) -> dict:
        """Fixture providing sample heading data."""
        return {
            "text": "Introduction",
            "level": 1,
            "html_snippet": "<h1>Introduction</h1>",
            "id_attr": "introduction",
        }

    def test_valid_heading(self, sample_heading_data: dict) -> None:
        """Test creating valid Heading."""
        heading = Heading(**sample_heading_data)
        assert heading.text == "Introduction"
        assert heading.level == 1
        assert heading.id_attr == "introduction"

    @pytest.mark.parametrize(
        "level",
        [1, 2, 3, 4, 5, 6],
    )
    def test_valid_heading_levels(self, sample_heading_data: dict, level: int) -> None:
        """Test all valid heading levels."""
        data = sample_heading_data.copy()
        data["level"] = level
        heading = Heading(**data)
        assert heading.level == level

    @pytest.mark.parametrize(
        "invalid_level",
        [0, 7, -1, 10],
    )
    def test_invalid_heading_levels(self, sample_heading_data: dict, invalid_level: int) -> None:
        """Test that invalid heading levels raise ValidationError."""
        data = sample_heading_data.copy()
        data["level"] = invalid_level
        with pytest.raises(ValidationError):
            Heading(**data)

    def test_heading_without_id(self, sample_heading_data: dict) -> None:
        """Test heading without id attribute."""
        data = sample_heading_data.copy()
        data["id_attr"] = None
        heading = Heading(**data)
        assert heading.id_attr is None


class TestImageBlock:
    """Tests for ImageBlock model."""

    @pytest.fixture
    def sample_image_block_data(self) -> dict:
        """Fixture providing sample image block data."""
        return {
            "src": "/images/logo.png",
            "alt": "Company Logo",
            "title": "Our Logo",
            "html_snippet": '<img src="/images/logo.png" alt="Company Logo">',
        }

    def test_valid_image_block(self, sample_image_block_data: dict) -> None:
        """Test creating valid ImageBlock."""
        block = ImageBlock(**sample_image_block_data)
        assert block.src == "/images/logo.png"
        assert block.alt == "Company Logo"
        assert block.title == "Our Logo"

    def test_image_without_alt(self, sample_image_block_data: dict) -> None:
        """Test image block without alt text."""
        data = sample_image_block_data.copy()
        data["alt"] = None
        block = ImageBlock(**data)
        assert block.alt is None

    def test_image_without_title(self, sample_image_block_data: dict) -> None:
        """Test image block without title."""
        data = sample_image_block_data.copy()
        data["title"] = None
        block = ImageBlock(**data)
        assert block.title is None


class TestLinkBlock:
    """Tests for LinkBlock model."""

    @pytest.fixture
    def sample_link_block_data(self) -> dict:
        """Fixture providing sample link block data."""
        return {
            "text": "Click here",
            "href": "https://example.com",
            "title": "Example Site",
            "is_external": True,
            "html_snippet": '<a href="https://example.com">Click here</a>',
        }

    def test_valid_link_block(self, sample_link_block_data: dict) -> None:
        """Test creating valid LinkBlock."""
        block = LinkBlock(**sample_link_block_data)
        assert block.text == "Click here"
        assert block.href == "https://example.com"
        assert block.is_external is True

    def test_internal_link(self, sample_link_block_data: dict) -> None:
        """Test internal link block."""
        data = sample_link_block_data.copy()
        data["is_external"] = False
        data["href"] = "/docs/guide"
        block = LinkBlock(**data)
        assert block.is_external is False

    def test_link_without_title(self, sample_link_block_data: dict) -> None:
        """Test link block without title."""
        data = sample_link_block_data.copy()
        data["title"] = None
        block = LinkBlock(**data)
        assert block.title is None


class TestSection:
    """Tests for Section model."""

    @pytest.fixture
    def sample_heading(self) -> Heading:
        """Fixture providing a sample heading."""
        return Heading(
            text="Section Title",
            level=2,
            html_snippet="<h2>Section Title</h2>",
        )

    @pytest.fixture
    def sample_text_block(self) -> TextBlock:
        """Fixture providing a sample text block."""
        return TextBlock(
            block_type="paragraph",
            text="Sample text",
            html_snippet="<p>Sample text</p>",
            char_count=11,
            word_count=2,
        )

    def test_empty_section(self) -> None:
        """Test creating empty section."""
        section = Section()
        assert section.heading is None
        assert len(section.text_blocks) == 0
        assert section.has_content is False

    def test_section_with_heading(self, sample_heading: Heading) -> None:
        """Test section with heading."""
        section = Section(heading=sample_heading)
        assert section.heading is not None
        assert section.heading.text == "Section Title"

    def test_section_with_content(self, sample_heading: Heading, sample_text_block: TextBlock) -> None:
        """Test section with content."""
        section = Section(
            heading=sample_heading,
            text_blocks=[sample_text_block],
        )
        assert section.has_content is True
        assert len(section.text_blocks) == 1

    def test_total_text_property(self, sample_heading: Heading, sample_text_block: TextBlock) -> None:
        """Test total_text property."""
        section = Section(
            heading=sample_heading,
            text_blocks=[sample_text_block],
        )
        assert "Section Title" in section.total_text
        assert "Sample text" in section.total_text

    def test_total_char_count_property(self, sample_text_block: TextBlock) -> None:
        """Test total_char_count property."""
        section = Section(text_blocks=[sample_text_block, sample_text_block])
        assert section.total_char_count == 22

    def test_section_nesting(self, sample_heading: Heading) -> None:
        """Test nested sections."""
        subsection = Section(heading=sample_heading, level=1)
        parent_section = Section(subsections=[subsection], level=0)
        assert len(parent_section.subsections) == 1
        assert parent_section.has_content is True

    @pytest.mark.parametrize(
        ("level", "expected"),
        [
            (0, 0),
            (1, 1),
            (5, 5),
        ],
    )
    def test_section_levels(self, level: int, expected: int) -> None:
        """Test section levels."""
        section = Section(level=level)
        assert section.level == expected


class TestDocumentMetadata:
    """Tests for DocumentMetadata model."""

    def test_empty_metadata(self) -> None:
        """Test creating empty metadata."""
        metadata = DocumentMetadata()
        assert metadata.title is None
        assert metadata.description is None
        assert len(metadata.keywords) == 0
        assert len(metadata.meta_tags) == 0

    def test_full_metadata(self) -> None:
        """Test creating metadata with all fields."""
        metadata = DocumentMetadata(
            title="Test Document",
            description="A test document",
            keywords=["test", "doc"],
            author="Test Author",
            meta_tags={"viewport": "width=device-width"},
            lang="en",
        )
        assert metadata.title == "Test Document"
        assert metadata.description == "A test document"
        assert len(metadata.keywords) == 2
        assert metadata.author == "Test Author"
        assert metadata.lang == "en"

    def test_metadata_defaults(self) -> None:
        """Test metadata field defaults."""
        metadata = DocumentMetadata(title="Test")
        assert metadata.keywords == []
        assert metadata.meta_tags == {}


class TestExtractedDocument:
    """Tests for ExtractedDocument model."""

    @pytest.fixture
    def sample_metadata(self) -> DocumentMetadata:
        """Fixture providing sample metadata."""
        return DocumentMetadata(title="Test Document")

    @pytest.fixture
    def sample_section(self) -> Section:
        """Fixture providing a sample section."""
        return Section(
            heading=Heading(text="Test", level=1, html_snippet="<h1>Test</h1>"),
        )

    def test_empty_document(self, sample_metadata: DocumentMetadata) -> None:
        """Test creating empty extracted document."""
        doc = ExtractedDocument(
            metadata=sample_metadata,
            sections=[],
            source_path="/test.html",
        )
        assert doc.section_count == 0
        assert doc.total_char_count == 0

    def test_document_with_sections(self, sample_metadata: DocumentMetadata, sample_section: Section) -> None:
        """Test document with sections."""
        doc = ExtractedDocument(
            metadata=sample_metadata,
            sections=[sample_section],
            source_path="/test.html",
        )
        assert doc.section_count == 1

    def test_heading_structure_property(self, sample_metadata: DocumentMetadata) -> None:
        """Test heading_structure property."""
        h1 = Heading(text="Title", level=1, html_snippet="<h1>Title</h1>")
        h2 = Heading(text="Subtitle", level=2, html_snippet="<h2>Subtitle</h2>")

        doc = ExtractedDocument(
            metadata=sample_metadata,
            sections=[],
            all_headings=[h1, h2],
            source_path="/test.html",
        )
        structure = doc.heading_structure
        assert len(structure) == 2
        assert structure[0] == (1, "Title")
        assert structure[1] == (2, "Subtitle")

    def test_document_aggregates(self, sample_metadata: DocumentMetadata) -> None:
        """Test document aggregates."""
        code_block = CodeBlock(
            code="test",
            html_snippet="<code>test</code>",
            line_count=1,
        )

        doc = ExtractedDocument(
            metadata=sample_metadata,
            sections=[],
            all_code_blocks=[code_block],
            source_path="/test.html",
            full_text="Test document text",
            total_char_count=18,
            total_word_count=3,
        )
        assert len(doc.all_code_blocks) == 1
        assert doc.full_text == "Test document text"
        assert doc.total_char_count == 18
        assert doc.total_word_count == 3
