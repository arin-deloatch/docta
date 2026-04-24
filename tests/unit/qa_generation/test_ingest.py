# pylint: disable=redefined-outer-name
"""Unit tests for qa_generation.ingest module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from docta.models.content import (
    CodeBlock,
    DocumentMetadata,
    ExtractedDocument,
    Heading,
    Section,
    TextBlock,
)
from docta.models.html_diff import HTMLChange, HTMLDiffReport, HTMLDiffResult
from docta.models.models import DeltaReport, DocumentRecord
from qa_generation.ingest.added_doc_converter import (
    _apply_length_filter,
    _assemble_section_content,
    _build_section_path,
    _flatten_sections,
    _get_topic_slug_from_document,
    _section_to_source_document,
    convert_added_documents,
)
from qa_generation.ingest.added_doc_processor import (
    DeltaReportReadError,
    extract_added_documents,
    read_delta_report,
)
from qa_generation.ingest.diff_report_reader import (
    DiffReportReadError,
    load_report_safe,
    read_diff_report,
)
from qa_generation.ingest.snippet_extractor import (
    _passes_change_type_filter,
    _passes_similarity_filter,
    _passes_text_length_filter,
    extract_snippets,
    extract_snippets_by_topic,
    preview_extraction,
)
from qa_generation.models import (
    AddedDocumentStats,
    FilterConfig,
    QASourceDocument,
    SnippetExtractionStats,
)

# --- diff_report_reader.py ---


class TestDiffReportReader:
    """Tests for diff report reading functions."""

    def test_read_diff_report_valid(self, tmp_path: Path) -> None:
        """Test reading a valid JSON diff report."""
        import json

        report_data = {
            "old_version": "1.0",
            "new_version": "2.0",
            "old_root": "/old",
            "new_root": "/new",
            "results": [],
            "total_compared": 0,
            "total_with_changes": 0,
        }
        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps(report_data))

        report = read_diff_report(report_file)
        assert report.old_version == "1.0"
        assert report.new_version == "2.0"

    def test_read_diff_report_invalid_json(self, tmp_path: Path) -> None:
        """Test invalid JSON raises DiffReportReadError."""
        report_file = tmp_path / "report.json"
        report_file.write_text("not json at all")

        with pytest.raises(DiffReportReadError, match="Invalid JSON"):
            read_diff_report(report_file)

    def test_read_diff_report_validation_failure(self, tmp_path: Path) -> None:
        """Test schema validation failure raises DiffReportReadError."""
        import json

        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps({"invalid": "schema"}))

        with pytest.raises(DiffReportReadError, match="validation failed"):
            read_diff_report(report_file)

    def test_read_diff_report_not_found(self) -> None:
        """Test nonexistent file raises DiffReportReadError."""
        with pytest.raises(DiffReportReadError, match="Security validation failed"):
            read_diff_report("/nonexistent/report.json")

    def test_read_diff_report_not_json_extension(self, tmp_path: Path) -> None:
        """Test non-JSON file extension raises DiffReportReadError."""
        report_file = tmp_path / "report.txt"
        report_file.write_text("{}")

        with pytest.raises(DiffReportReadError):
            read_diff_report(report_file)

    def test_read_diff_report_json_array_root(self, tmp_path: Path) -> None:
        """Test JSON array root type raises DiffReportReadError."""
        report_file = tmp_path / "report.json"
        report_file.write_text("[1, 2, 3]")

        with pytest.raises(DiffReportReadError, match="Invalid JSON root type"):
            read_diff_report(report_file)

    def test_load_report_safe_returns_none_on_error(self) -> None:
        """Test load_report_safe returns None on read error."""
        result = load_report_safe("/nonexistent/report.json")
        assert result is None

    def test_load_report_safe_returns_report(self, tmp_path: Path) -> None:
        """Test load_report_safe returns report on success."""
        import json

        report_data = {
            "old_version": "1.0",
            "new_version": "2.0",
            "old_root": "/old",
            "new_root": "/new",
            "results": [],
            "total_compared": 0,
            "total_with_changes": 0,
        }
        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps(report_data))

        report = load_report_safe(report_file)
        assert report is not None
        assert report.old_version == "1.0"


# --- added_doc_processor.py ---


class TestAddedDocProcessor:
    """Tests for added document processing functions."""

    def test_read_delta_report_valid(self, tmp_path: Path) -> None:
        """Test reading a valid delta report."""
        import json

        report_data = {
            "old_version": "1.0",
            "new_version": "2.0",
            "unchanged": [],
            "modified": [],
            "renamed_candidates": [],
            "removed": [],
            "added": [],
        }
        report_file = tmp_path / "delta.json"
        report_file.write_text(json.dumps(report_data))

        report = read_delta_report(report_file)
        assert report.old_version == "1.0"

    def test_read_delta_report_invalid_json(self, tmp_path: Path) -> None:
        """Test invalid JSON raises DeltaReportReadError."""
        report_file = tmp_path / "delta.json"
        report_file.write_text("{{bad json}}")

        with pytest.raises(DeltaReportReadError, match="Invalid JSON"):
            read_delta_report(report_file)

    def test_read_delta_report_validation_failure(self, tmp_path: Path) -> None:
        """Test schema validation failure raises DeltaReportReadError."""
        import json

        report_file = tmp_path / "delta.json"
        report_file.write_text(json.dumps({"bad": "schema"}))

        with pytest.raises(DeltaReportReadError, match="validation failed"):
            read_delta_report(report_file)

    def test_extract_added_documents_no_docs(
        self,
        sample_added_doc_stats: AddedDocumentStats,
    ) -> None:
        """Test extraction with no added documents returns empty list."""
        delta = DeltaReport(
            old_version="1",
            new_version="2",
            unchanged=[],
            modified=[],
            renamed_candidates=[],
            removed=[],
            added=[],
        )
        config = FilterConfig()
        result = extract_added_documents(delta, config, sample_added_doc_stats)
        assert not result
        assert sample_added_doc_stats.total_added_docs == 0

    @patch("qa_generation.ingest.added_doc_processor.extract_document_content")
    def test_extract_added_documents_success(
        self,
        mock_extract: MagicMock,
        tmp_path: Path,
        sample_added_doc_stats: AddedDocumentStats,
    ) -> None:
        """Test successful extraction of added documents."""
        html_file = tmp_path / "new_guide.html"
        html_file.write_text("<html><body>Content</body></html>")

        doc_record = DocumentRecord(
            version="2.0",
            root=str(tmp_path),
            relative_path="new_guide.html",
            topic_slug="new-guide",
            html_filename="new_guide.html",
            raw_hash="abc",
        )
        delta = DeltaReport(
            old_version="1",
            new_version="2",
            unchanged=[],
            modified=[],
            renamed_candidates=[],
            removed=[],
            added=[doc_record],
        )

        mock_doc = MagicMock(spec=ExtractedDocument)
        mock_doc.sections = []
        mock_extract.return_value = mock_doc

        config = FilterConfig()
        result = extract_added_documents(delta, config, sample_added_doc_stats)
        assert len(result) == 1
        assert sample_added_doc_stats.total_added_docs == 1

    def test_extract_added_documents_file_not_found(
        self,
        sample_added_doc_stats: AddedDocumentStats,
    ) -> None:
        """Test missing HTML file increments filtered_invalid_html counter."""
        doc_record = DocumentRecord(
            version="2.0",
            root="/nonexistent",
            relative_path="missing.html",
            topic_slug="missing",
            html_filename="missing.html",
            raw_hash="abc",
        )
        delta = DeltaReport(
            old_version="1",
            new_version="2",
            unchanged=[],
            modified=[],
            renamed_candidates=[],
            removed=[],
            added=[doc_record],
        )
        config = FilterConfig()
        result = extract_added_documents(delta, config, sample_added_doc_stats)
        assert not result
        assert sample_added_doc_stats.filtered_invalid_html == 1

    @patch("qa_generation.ingest.added_doc_processor.extract_document_content")
    def test_extract_added_documents_max_documents(
        self,
        mock_extract: MagicMock,
        tmp_path: Path,
        sample_added_doc_stats: AddedDocumentStats,
    ) -> None:
        """Test max_documents limits the number of extracted documents."""
        records = []
        for i in range(5):
            html_file = tmp_path / f"doc{i}.html"
            html_file.write_text(f"<html>Doc {i}</html>")
            records.append(
                DocumentRecord(
                    version="2.0",
                    root=str(tmp_path),
                    relative_path=f"doc{i}.html",
                    topic_slug=f"doc-{i}",
                    html_filename=f"doc{i}.html",
                    raw_hash=f"hash{i}",
                )
            )

        delta = DeltaReport(
            old_version="1",
            new_version="2",
            unchanged=[],
            modified=[],
            renamed_candidates=[],
            removed=[],
            added=records,
        )

        mock_doc = ExtractedDocument(
            metadata=DocumentMetadata(title="Test"),
            sections=[],
            source_path="/tmp/test.html",
            total_char_count=100,
            total_word_count=10,
        )
        mock_extract.return_value = mock_doc

        config = FilterConfig()
        result = extract_added_documents(delta, config, sample_added_doc_stats, max_documents=2)
        assert len(result) == 2


# --- added_doc_converter.py ---


class TestAddedDocConverter:
    """Tests for added document conversion functions."""

    def test_assemble_section_content(
        self,
        sample_heading: Heading,
        sample_text_block: TextBlock,
        sample_code_block: CodeBlock,
    ) -> None:
        """Test section content assembly includes heading, text, and code."""
        section = Section(
            heading=sample_heading,
            text_blocks=[sample_text_block],
            code_blocks=[sample_code_block],
        )
        content = _assemble_section_content(section)
        assert "Installation" in content
        assert "Install the package using pip." in content
        assert "pip install foo" in content

    def test_assemble_section_content_empty(self) -> None:
        """Test empty section produces empty content string."""
        section = Section()
        content = _assemble_section_content(section)
        assert content == ""

    def test_build_section_path_root(self, sample_heading: Heading) -> None:
        """Test root section path uses heading text."""
        section = Section(heading=sample_heading)
        path = _build_section_path(section)
        assert path == "Installation"

    def test_build_section_path_nested(self, sample_heading: Heading) -> None:
        """Test nested section path joins parent and heading."""
        section = Section(heading=sample_heading)
        path = _build_section_path(section, parent_path="Getting Started")
        assert path == "Getting Started > Installation"

    def test_build_section_path_no_heading(self) -> None:
        """Test section without heading uses parent path."""
        section = Section()
        path = _build_section_path(section, parent_path="Parent")
        assert path == "Parent"

    def test_section_to_source_document(self, sample_section: Section) -> None:
        """Test converting a section to a source document."""
        doc = _section_to_source_document(sample_section, "test-topic", "2.0")
        assert doc is not None
        assert doc.topic_slug == "test-topic"
        assert doc.change_type == "document_added"
        assert doc.location is not None
        assert "Installation" in doc.location  # pylint: disable=unsupported-membership-test

    def test_section_to_source_document_empty(self) -> None:
        """Test empty section returns None."""
        section = Section()
        doc = _section_to_source_document(section, "test-topic", "2.0")
        assert doc is None

    def test_flatten_sections_recursive(self) -> None:
        """Test recursive flattening of nested sections."""
        child_heading = Heading(text="Prerequisites", level=3, html_snippet="<h3>Prerequisites</h3>")
        child_text = TextBlock(
            block_type="paragraph",
            text="You need Python 3.11+",
            html_snippet="<p>You need Python 3.11+</p>",
            char_count=20,
            word_count=4,
        )
        child = Section(heading=child_heading, text_blocks=[child_text])

        parent_heading = Heading(text="Installation", level=2, html_snippet="<h2>Installation</h2>")
        parent_text = TextBlock(
            block_type="paragraph",
            text="Follow these steps to install.",
            html_snippet="<p>Follow these steps to install.</p>",
            char_count=30,
            word_count=5,
        )
        parent = Section(
            heading=parent_heading,
            text_blocks=[parent_text],
            subsections=[child],
        )

        docs = _flatten_sections(parent, "test", "2.0")
        assert len(docs) == 2
        assert docs[1].location == "Installation > Prerequisites"

    def test_apply_length_filter(self) -> None:
        """Test length filter removes documents outside bounds."""
        config = FilterConfig(min_text_length=10, max_text_length=100)
        stats = AddedDocumentStats()
        docs = [
            QASourceDocument(content="short", topic_slug="t"),
            QASourceDocument(content="this is long enough to pass the filter", topic_slug="t"),
            QASourceDocument(content="x" * 200, topic_slug="t"),
        ]
        filtered = _apply_length_filter(docs, config, stats)
        assert len(filtered) == 1
        assert stats.filtered_by_length == 2

    def test_get_topic_slug_from_document(
        self,
        sample_extracted_document: ExtractedDocument,
        sample_delta_report: DeltaReport,
    ) -> None:
        """Test topic slug extraction from document and delta report."""
        slug = _get_topic_slug_from_document(sample_extracted_document, sample_delta_report)
        assert slug is None or isinstance(slug, str)

    def test_get_topic_slug_by_filename(self) -> None:
        """Test topic slug lookup by matching filename."""
        doc_record = DocumentRecord(
            version="2.0",
            root="/docs",
            relative_path="guide.html",
            topic_slug="guide",
            html_filename="guide.html",
            raw_hash="abc",
        )
        delta = DeltaReport(
            old_version="1",
            new_version="2",
            unchanged=[],
            modified=[],
            renamed_candidates=[],
            removed=[],
            added=[doc_record],
        )
        extracted = ExtractedDocument(
            metadata=DocumentMetadata(title="Guide"),
            sections=[],
            source_path="/other/path/guide.html",
            total_char_count=0,
            total_word_count=0,
        )
        slug = _get_topic_slug_from_document(extracted, delta)
        assert slug == "guide"

    def test_get_topic_slug_not_found(self) -> None:
        """Test topic slug returns None when no match found."""
        delta = DeltaReport(
            old_version="1",
            new_version="2",
            unchanged=[],
            modified=[],
            renamed_candidates=[],
            removed=[],
            added=[],
        )
        extracted = ExtractedDocument(
            metadata=DocumentMetadata(title="Unknown"),
            sections=[],
            source_path="/docs/unknown.html",
            total_char_count=0,
            total_word_count=0,
        )
        slug = _get_topic_slug_from_document(extracted, delta)
        assert slug is None

    def test_convert_added_documents_empty(self) -> None:
        """Test converting empty document list returns empty result."""
        delta = DeltaReport(
            old_version="1",
            new_version="2",
            unchanged=[],
            modified=[],
            renamed_candidates=[],
            removed=[],
            added=[],
        )
        config = FilterConfig(min_text_length=1, max_text_length=10000)
        stats = AddedDocumentStats()
        result = convert_added_documents([], delta, config, stats)
        assert not result

    def test_convert_added_documents_with_sections(self) -> None:
        """Test converting documents with sections creates source documents."""
        doc_record = DocumentRecord(
            version="2.0",
            root="/docs",
            relative_path="guide.html",
            topic_slug="guide",
            html_filename="guide.html",
            raw_hash="abc",
        )
        delta = DeltaReport(
            old_version="1",
            new_version="2",
            unchanged=[],
            modified=[],
            renamed_candidates=[],
            removed=[],
            added=[doc_record],
        )

        heading = Heading(text="Installation", level=2, html_snippet="<h2>Installation</h2>")
        text_block = TextBlock(
            block_type="paragraph",
            text="A" * 100,
            html_snippet=f"<p>{'A' * 100}</p>",
            char_count=100,
            word_count=1,
        )
        section = Section(heading=heading, text_blocks=[text_block])
        extracted = ExtractedDocument(
            metadata=DocumentMetadata(title="Guide"),
            sections=[section],
            source_path="/docs/guide.html",
            total_char_count=100,
            total_word_count=1,
        )

        config = FilterConfig(min_text_length=10, max_text_length=10000)
        stats = AddedDocumentStats()
        result = convert_added_documents([extracted], delta, config, stats)
        assert len(result) >= 1
        assert result[0].topic_slug == "guide"
        assert result[0].change_type == "document_added"


# --- snippet_extractor.py ---


class TestSnippetExtractor:
    """Tests for snippet extraction functions."""

    def test_passes_change_type_filter_true(self) -> None:
        """Test matching change type passes filter."""
        change = HTMLChange(change_type="text_change", description="d")
        config = FilterConfig(change_types={"text_change"})
        assert _passes_change_type_filter(change, config) is True

    def test_passes_change_type_filter_false(self) -> None:
        """Test non-matching change type fails filter."""
        change = HTMLChange(change_type="structure_change", description="d")
        config = FilterConfig(change_types={"text_change"})
        assert _passes_change_type_filter(change, config) is False

    def test_passes_text_length_filter(self) -> None:
        """Test text length filter with in-range and out-of-range values."""
        config = FilterConfig(min_text_length=5, max_text_length=100)
        assert _passes_text_length_filter("hello world", config) is True
        assert _passes_text_length_filter("hi", config) is False
        assert _passes_text_length_filter("x" * 200, config) is False

    def test_passes_similarity_filter(self) -> None:
        """Test similarity filter with in-range and out-of-range values."""
        result = HTMLDiffResult(
            old_path="a.html",
            new_path="b.html",
            old_topic_slug="t",
            new_topic_slug="t",
            relationship="modified",
            changes=[],
            text_similarity=50.0,
            has_structural_changes=False,
        )
        config = FilterConfig(min_similarity=30.0, max_similarity=70.0)
        assert _passes_similarity_filter(result, config) is True

        config_out = FilterConfig(min_similarity=60.0, max_similarity=90.0)
        assert _passes_similarity_filter(result, config_out) is False

    def test_extract_snippets_empty_change_types(
        self,
        sample_html_diff_report: HTMLDiffReport,
    ) -> None:
        """Test empty change_types set raises ValueError."""
        config = FilterConfig(change_types=set())
        with pytest.raises(ValueError, match="cannot be empty"):
            extract_snippets(sample_html_diff_report, config)

    def test_extract_snippets_basic(self, sample_html_diff_report: HTMLDiffReport) -> None:
        """Test basic snippet extraction from a diff report."""
        config = FilterConfig(
            min_text_length=5,
            max_text_length=5000,
            change_types={"text_change"},
            min_similarity=0.0,
            max_similarity=100.0,
        )
        snippets, stats = extract_snippets(sample_html_diff_report, config)
        assert len(snippets) == 1
        assert stats.extracted_snippets == 1
        assert snippets[0].topic_slug == "guide"

    def test_extract_snippets_filtered_by_similarity(self) -> None:
        """Test snippets are filtered when similarity exceeds threshold."""
        change = HTMLChange(
            change_type="text_change",
            description="d",
            new_text="some text content here",
        )
        result = HTMLDiffResult(
            old_path="a.html",
            new_path="b.html",
            old_topic_slug="t",
            new_topic_slug="t",
            relationship="modified",
            changes=[change],
            text_similarity=98.0,
            has_structural_changes=False,
        )
        report = HTMLDiffReport(
            old_version="1",
            new_version="2",
            old_root="/old",
            new_root="/new",
            results=[result],
            total_compared=1,
            total_with_changes=1,
        )
        config = FilterConfig(
            min_text_length=5,
            max_text_length=5000,
            change_types={"text_change"},
            max_similarity=95.0,
        )
        snippets, stats = extract_snippets(report, config)
        assert len(snippets) == 0
        assert stats.filtered_by_similarity == 1

    def test_extract_snippets_max_documents(self) -> None:
        """Test max_documents limits extracted snippet count."""
        changes = [
            HTMLChange(
                change_type="text_change",
                description=f"change {i}",
                new_text=f"content number {i} with enough text",
            )
            for i in range(5)
        ]
        result = HTMLDiffResult(
            old_path="a.html",
            new_path="b.html",
            old_topic_slug="t",
            new_topic_slug="t",
            relationship="modified",
            changes=changes,
            text_similarity=50.0,
            has_structural_changes=False,
        )
        report = HTMLDiffReport(
            old_version="1",
            new_version="2",
            old_root="/old",
            new_root="/new",
            results=[result],
            total_compared=1,
            total_with_changes=1,
        )
        config = FilterConfig(
            min_text_length=5,
            max_text_length=5000,
            change_types={"text_change"},
        )
        snippets, _stats = extract_snippets(report, config, max_documents=2)
        assert len(snippets) == 2

    def test_extract_snippets_change_without_text_filtered(self) -> None:
        """Test changes without text content are filtered out."""
        change = HTMLChange(
            change_type="text_change",
            description="d",
            old_text=None,
            new_text=None,
        )
        result = HTMLDiffResult(
            old_path="a.html",
            new_path="b.html",
            old_topic_slug="topic",
            new_topic_slug="topic",
            relationship="modified",
            changes=[change],
            text_similarity=50.0,
            has_structural_changes=False,
        )
        report = HTMLDiffReport(
            old_version="1",
            new_version="2",
            old_root="/old",
            new_root="/new",
            results=[result],
            total_compared=1,
            total_with_changes=1,
        )
        config = FilterConfig(
            min_text_length=5,
            max_text_length=5000,
            change_types={"text_change"},
        )
        snippets, stats = extract_snippets(report, config)
        assert len(snippets) == 0
        assert stats.filtered_no_text == 1

    def test_extract_snippets_by_topic(self) -> None:
        """Test snippets are grouped by topic slug."""
        changes1 = [
            HTMLChange(change_type="text_change", description="d", new_text="content for topic A"),
        ]
        changes2 = [
            HTMLChange(change_type="text_change", description="d", new_text="content for topic B"),
        ]
        result1 = HTMLDiffResult(
            old_path="a.html",
            new_path="a2.html",
            old_topic_slug="topic-a",
            new_topic_slug="topic-a",
            relationship="modified",
            changes=changes1,
            text_similarity=50.0,
            has_structural_changes=False,
        )
        result2 = HTMLDiffResult(
            old_path="b.html",
            new_path="b2.html",
            old_topic_slug="topic-b",
            new_topic_slug="topic-b",
            relationship="modified",
            changes=changes2,
            text_similarity=50.0,
            has_structural_changes=False,
        )
        report = HTMLDiffReport(
            old_version="1",
            new_version="2",
            old_root="/old",
            new_root="/new",
            results=[result1, result2],
            total_compared=2,
            total_with_changes=2,
        )
        config = FilterConfig(
            min_text_length=5,
            max_text_length=5000,
            change_types={"text_change"},
        )
        by_topic = extract_snippets_by_topic(report, config)
        assert "topic-a" in by_topic
        assert "topic-b" in by_topic

    def test_preview_extraction(self, sample_html_diff_report: HTMLDiffReport) -> None:
        """Test preview_extraction returns stats without documents."""
        config = FilterConfig(
            min_text_length=5,
            max_text_length=5000,
            change_types={"text_change"},
            min_similarity=0.0,
            max_similarity=100.0,
        )
        stats = preview_extraction(sample_html_diff_report, config)
        assert stats.extracted_snippets == 1
        assert isinstance(stats, SnippetExtractionStats)

    def test_preview_extraction_empty_change_types(
        self,
        sample_html_diff_report: HTMLDiffReport,
    ) -> None:
        """Test preview with empty change_types raises ValueError."""
        config = FilterConfig(change_types=set())
        with pytest.raises(ValueError, match="cannot be empty"):
            preview_extraction(sample_html_diff_report, config)

    def test_extract_snippets_empty_report(self) -> None:
        """Test extraction from empty report returns empty list."""
        report = HTMLDiffReport(
            old_version="1",
            new_version="2",
            old_root="/old",
            new_root="/new",
            results=[],
            total_compared=0,
            total_with_changes=0,
        )
        config = FilterConfig(change_types={"text_change"})
        snippets, stats = extract_snippets(report, config)
        assert len(snippets) == 0
        assert stats.total_results == 0
