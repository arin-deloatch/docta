"""Unit tests for qa_generation.models module."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from docta.models.html_diff import HTMLChange, HTMLDiffReport, HTMLDiffResult
from qa_generation.models import (
    AddedDocumentStats,
    EmbeddingConfig,
    FilterConfig,
    GeneratorConfig,
    LLMConfig,
    QAPair,
    QASourceDocument,
    QueryDistribution,
    SnippetExtractionStats,
    SourceDocumentInfo,
)
from qa_generation.models.report_ingestion import (
    count_text_changes,
    filter_by_change_type,
    filter_by_similarity,
    get_primary_text,
    get_text_changes,
)

# --- SnippetExtractionStats ---


class TestSnippetExtractionStats:
    """Tests for SnippetExtractionStats model."""

    def test_defaults(self) -> None:
        """Test default values are zero."""
        stats = SnippetExtractionStats()
        assert stats.total_results == 0
        assert stats.total_changes == 0
        assert stats.extracted_snippets == 0

    def test_total_filtered(self) -> None:
        """Test total_filtered sums all filter counts."""
        stats = SnippetExtractionStats(
            filtered_by_type=3,
            filtered_by_length=2,
            filtered_by_similarity=1,
            filtered_no_text=4,
            filtered_no_topic_slug=1,
        )
        assert stats.total_filtered == 11

    def test_extraction_rate_with_changes(self) -> None:
        """Test extraction_rate computes correct percentage."""
        stats = SnippetExtractionStats(total_changes=100, extracted_snippets=25)
        assert stats.extraction_rate == 25.0

    def test_extraction_rate_zero_changes(self) -> None:
        """Test extraction_rate returns zero when no changes exist."""
        stats = SnippetExtractionStats(total_changes=0)
        assert stats.extraction_rate == 0.0

    def test_to_dict(self) -> None:
        """Test to_dict returns all fields as a dictionary."""
        stats = SnippetExtractionStats(
            total_results=10,
            total_changes=50,
            extracted_snippets=20,
            filtered_by_type=5,
            filtered_by_length=10,
            filtered_by_similarity=3,
            filtered_no_text=7,
            filtered_no_topic_slug=5,
        )
        d = stats.to_dict()
        assert d["total_results"] == 10
        assert d["total_changes"] == 50
        assert d["extracted_snippets"] == 20
        assert d["filtered_by_type"] == 5

    def test_negative_values_rejected(self) -> None:
        """Test negative values raise validation error."""
        with pytest.raises(ValidationError):
            SnippetExtractionStats(total_results=-1)


# --- AddedDocumentStats ---


class TestAddedDocumentStats:
    """Tests for AddedDocumentStats model."""

    def test_defaults(self) -> None:
        """Test default values are zero."""
        stats = AddedDocumentStats()
        assert stats.total_added_docs == 0
        assert stats.converted_sources == 0

    def test_total_filtered(self) -> None:
        """Test total_filtered sums all filter counts."""
        stats = AddedDocumentStats(
            filtered_by_length=3,
            filtered_no_content=2,
            filtered_invalid_html=1,
        )
        assert stats.total_filtered == 6

    def test_conversion_rate_with_sections(self) -> None:
        """Test conversion_rate computes correct percentage."""
        stats = AddedDocumentStats(
            total_sections_extracted=100,
            converted_sources=80,
        )
        assert stats.conversion_rate == 80.0

    def test_conversion_rate_zero_sections(self) -> None:
        """Test conversion_rate returns zero when no sections exist."""
        stats = AddedDocumentStats(total_sections_extracted=0)
        assert stats.conversion_rate == 0.0

    def test_to_dict_includes_conversion_rate(self) -> None:
        """Test to_dict includes the computed conversion_rate field."""
        stats = AddedDocumentStats(
            total_added_docs=5,
            total_sections_extracted=50,
            converted_sources=40,
        )
        d = stats.to_dict()
        assert d["total_added_docs"] == 5
        assert d["conversion_rate"] == 80.0


# --- LLMConfig and EmbeddingConfig ---


class TestProviderConfig:
    """Tests for LLMConfig and EmbeddingConfig models."""

    def test_llm_config_defaults(self) -> None:
        """Test LLMConfig default values."""
        config = LLMConfig()
        assert config.provider == "openai"
        assert config.model == "gpt-4o"
        assert config.temperature == 0.3
        assert config.max_tokens is None

    def test_llm_config_custom(self) -> None:
        """Test LLMConfig accepts custom provider and model."""
        config = LLMConfig(
            provider="google",
            model="gemini-pro",
            temperature=0.7,
            max_tokens=4096,
        )
        assert config.provider == "google"
        assert config.max_tokens == 4096

    def test_llm_config_temperature_bounds(self) -> None:
        """Test temperature validation rejects out-of-range values."""
        LLMConfig(temperature=0.0)
        LLMConfig(temperature=2.0)
        with pytest.raises(ValidationError):
            LLMConfig(temperature=-0.1)
        with pytest.raises(ValidationError):
            LLMConfig(temperature=2.1)

    def test_embedding_config_defaults(self) -> None:
        """Test EmbeddingConfig default values."""
        config = EmbeddingConfig()
        assert config.provider == "openai"
        assert config.model == "text-embedding-3-small"


# --- QueryDistribution ---


class TestQueryDistribution:
    """Tests for QueryDistribution model."""

    def test_default_sums_to_one(self) -> None:
        """Test default weights sum to 1.0."""
        dist = QueryDistribution()
        assert abs(dist.specific + dist.abstract + dist.comparative - 1.0) < 0.01

    def test_valid_distribution(self) -> None:
        """Test valid custom distribution is accepted."""
        dist = QueryDistribution(specific=0.6, abstract=0.2, comparative=0.2)
        assert dist.specific == 0.6

    def test_invalid_distribution_sum(self) -> None:
        """Test weights not summing to 1.0 raise validation error."""
        with pytest.raises(ValidationError, match="sum to 1.0"):
            QueryDistribution(specific=0.5, abstract=0.5, comparative=0.5)

    def test_zero_weights_allowed(self) -> None:
        """Test zero-weight categories are allowed when sum is 1.0."""
        dist = QueryDistribution(specific=1.0, abstract=0.0, comparative=0.0)
        assert dist.specific == 1.0

    @pytest.mark.parametrize("field", ["specific", "abstract", "comparative"])
    def test_negative_weights_rejected(self, field: str) -> None:
        """Test negative weight values are rejected."""
        with pytest.raises(ValidationError):
            QueryDistribution(**{field: -0.1})


# --- FilterConfig ---


class TestFilterConfig:
    """Tests for FilterConfig model."""

    def test_defaults(self) -> None:
        """Test FilterConfig default values."""
        config = FilterConfig()
        assert config.min_text_length == 50
        assert config.max_text_length == 10000
        assert "text_change" in config.change_types

    def test_min_greater_than_max_text_length(self) -> None:
        """Test min_text_length greater than max raises validation error."""
        with pytest.raises(ValidationError, match="min_text_length"):
            FilterConfig(min_text_length=100, max_text_length=50)

    def test_min_greater_than_max_similarity(self) -> None:
        """Test min_similarity greater than max raises validation error."""
        with pytest.raises(ValidationError, match="min_similarity"):
            FilterConfig(min_similarity=90.0, max_similarity=10.0)

    def test_valid_ranges(self) -> None:
        """Test valid range values are accepted."""
        config = FilterConfig(
            min_text_length=0,
            max_text_length=100,
            min_similarity=10.0,
            max_similarity=90.0,
        )
        assert config.min_text_length == 0


# --- SourceDocumentInfo ---


class TestSourceDocumentInfo:
    """Tests for SourceDocumentInfo model."""

    def test_basic_creation(self, sample_source_document_info: SourceDocumentInfo) -> None:
        """Test basic field access on a valid instance."""
        assert sample_source_document_info.topic_slug == "guide"
        assert sample_source_document_info.versions == ("1.0.0", "2.0.0")

    def test_metadata_validation_too_many_keys(self) -> None:
        """Test metadata with more than 100 keys raises validation error."""
        with pytest.raises(ValidationError, match="metadata"):
            SourceDocumentInfo(
                topic_slug="test",
                metadata={f"key_{i}": f"val_{i}" for i in range(101)},
            )

    def test_metadata_non_serializable_rejected(self) -> None:
        """Test non-JSON-serializable metadata values are rejected."""
        with pytest.raises(ValidationError, match="JSON-serializable"):
            SourceDocumentInfo(
                topic_slug="test",
                metadata={"bad": object()},
            )


# --- QASourceDocument ---


class TestQASourceDocument:
    """Tests for QASourceDocument model."""

    def test_basic_creation(self, sample_qa_source_document: QASourceDocument) -> None:
        """Test basic field access on a valid instance."""
        assert sample_qa_source_document.topic_slug == "guide"
        assert sample_qa_source_document.change_type == "text_change"

    def test_char_count(self) -> None:
        """Test char_count returns content length."""
        doc = QASourceDocument(content="hello world", topic_slug="test")
        assert doc.char_count == 11

    def test_word_count(self) -> None:
        """Test word_count returns number of words in content."""
        doc = QASourceDocument(content="hello world foo", topic_slug="test")
        assert doc.word_count == 3

    def test_from_html_change(self) -> None:
        """Test from_html_change creates document from HTMLChange."""
        change = HTMLChange(
            change_type="text_change",
            description="Updated text",
            old_text="old content here",
            new_text="new content here that is long enough",
            location="Section A",
        )
        doc = QASourceDocument.from_html_change(change, topic_slug="test-topic")
        assert doc.content == "new content here that is long enough"
        assert doc.topic_slug == "test-topic"
        assert doc.location == "Section A"
        assert doc.change_type == "text_change"

    def test_from_html_change_with_report(
        self,
        sample_html_change: HTMLChange,
        sample_html_diff_report: HTMLDiffReport,
    ) -> None:
        """Test from_html_change includes version metadata from report."""
        doc = QASourceDocument.from_html_change(
            sample_html_change,
            topic_slug="guide",
            report=sample_html_diff_report,
        )
        assert doc.metadata["versions"]["old"] == "1.0.0"
        assert doc.metadata["versions"]["new"] == "2.0.0"

    def test_from_html_change_prefers_new_text(self) -> None:
        """Test from_html_change uses new_text over old_text."""
        change = HTMLChange(
            change_type="text_change",
            description="test",
            old_text="old",
            new_text="new",
        )
        doc = QASourceDocument.from_html_change(change, topic_slug="t")
        assert doc.content == "new"

    def test_from_html_change_falls_back_to_old_text(self) -> None:
        """Test from_html_change falls back to old_text when new_text is None."""
        change = HTMLChange(
            change_type="text_change",
            description="test",
            old_text="old content",
            new_text=None,
        )
        doc = QASourceDocument.from_html_change(change, topic_slug="t")
        assert doc.content == "old content"

    def test_from_html_change_no_text_raises(self) -> None:
        """Test from_html_change raises ValueError when both texts are None."""
        change = HTMLChange(
            change_type="text_change",
            description="test",
            old_text=None,
            new_text=None,
        )
        with pytest.raises(ValueError, match="must have either new_text or old_text"):
            QASourceDocument.from_html_change(change, topic_slug="t")

    def test_metadata_too_many_keys(self) -> None:
        """Test metadata with more than 100 keys raises validation error."""
        with pytest.raises(ValidationError, match="metadata"):
            QASourceDocument(
                content="test",
                topic_slug="test",
                metadata={f"key_{i}": f"val_{i}" for i in range(101)},
            )


# --- QAPair ---


class TestQAPair:
    """Tests for QAPair model."""

    def test_basic_creation(self, sample_qa_pair: QAPair) -> None:
        """Test basic field access on a valid instance."""
        assert sample_qa_pair.question == "How do you install foo?"
        assert sample_qa_pair.source_topic_slug == "guide"

    def test_question_length(self) -> None:
        """Test question_length returns character count of question."""
        qa = QAPair(
            question="What?",
            ground_truth_answer="Something.",
            source_topic_slug="t",
        )
        assert qa.question_length == 5

    def test_answer_length(self) -> None:
        """Test answer_length returns character count of answer."""
        qa = QAPair(
            question="What?",
            ground_truth_answer="Something.",
            source_topic_slug="t",
        )
        assert qa.answer_length == 10

    def test_has_traceability_true(self, sample_qa_pair: QAPair) -> None:
        """Test has_traceability returns True when all fields are set."""
        assert sample_qa_pair.has_traceability is True

    def test_has_traceability_false_missing_location(self) -> None:
        """Test has_traceability returns False when location is missing."""
        qa = QAPair(
            question="Q?",
            ground_truth_answer="A.",
            source_topic_slug="t",
        )
        assert qa.has_traceability is False

    def test_has_traceability_false_missing_versions(self) -> None:
        """Test has_traceability returns False when versions is None."""
        qa = QAPair(
            question="Q?",
            ground_truth_answer="A.",
            source_topic_slug="t",
            source_location="loc",
            source_change_type="text_change",
            source_versions=None,
        )
        assert qa.has_traceability is False

    def test_metadata_non_serializable_rejected(self) -> None:
        """Test non-JSON-serializable metadata values are rejected."""
        with pytest.raises(ValidationError, match="JSON-serializable"):
            QAPair(
                question="Q?",
                ground_truth_answer="A.",
                source_topic_slug="t",
                metadata={"bad": object()},
            )


# --- GeneratorConfig ---


class TestGeneratorConfig:
    """Tests for GeneratorConfig model."""

    def test_defaults(self) -> None:
        """Test GeneratorConfig default values."""
        config = GeneratorConfig()
        assert config.testset_size == 50
        assert config.seed is None

    def test_custom_values(self) -> None:
        """Test GeneratorConfig accepts custom testset_size and seed."""
        config = GeneratorConfig(testset_size=100, seed=42)
        assert config.testset_size == 100
        assert config.seed == 42

    def test_invalid_testset_size(self) -> None:
        """Test testset_size of zero raises validation error."""
        with pytest.raises(ValidationError):
            GeneratorConfig(testset_size=0)


# --- report_ingestion functions ---


class TestGetTextChanges:
    """Tests for get_text_changes function."""

    def test_returns_text_changes_with_content(self) -> None:
        """Test only text_change items with content are returned."""
        changes = [
            HTMLChange(change_type="text_change", description="d", new_text="some text"),
            HTMLChange(change_type="structure_change", description="d", new_text="x"),
            HTMLChange(change_type="text_change", description="d"),
        ]
        result = HTMLDiffResult(
            old_path="a.html",
            new_path="b.html",
            old_topic_slug="t",
            new_topic_slug="t",
            relationship="modified",
            changes=changes,
            text_similarity=50.0,
            has_structural_changes=True,
        )
        text_changes = get_text_changes(result)
        assert len(text_changes) == 1
        assert text_changes[0].new_text == "some text"

    def test_empty_changes(self) -> None:
        """Test empty changes list returns empty result."""
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
        assert get_text_changes(result) == []


class TestFilterBySimilarity:
    """Tests for filter_by_similarity function."""

    def test_filters_by_range(self, sample_html_diff_report: HTMLDiffReport) -> None:
        """Test results within similarity range are included."""
        filtered = filter_by_similarity(sample_html_diff_report, 70.0, 80.0)
        assert len(filtered) == 1

    def test_excludes_outside_range(self, sample_html_diff_report: HTMLDiffReport) -> None:
        """Test results outside similarity range are excluded."""
        filtered = filter_by_similarity(sample_html_diff_report, 80.0, 90.0)
        assert len(filtered) == 0

    def test_invalid_min_similarity(self, sample_html_diff_report: HTMLDiffReport) -> None:
        """Test negative min_similarity raises ValueError."""
        with pytest.raises(ValueError, match="min_similarity"):
            filter_by_similarity(sample_html_diff_report, -1.0)

    def test_invalid_max_similarity(self, sample_html_diff_report: HTMLDiffReport) -> None:
        """Test max_similarity over 100 raises ValueError."""
        with pytest.raises(ValueError, match="max_similarity"):
            filter_by_similarity(sample_html_diff_report, 0.0, 101.0)

    def test_min_greater_than_max(self, sample_html_diff_report: HTMLDiffReport) -> None:
        """Test min_similarity greater than max raises ValueError."""
        with pytest.raises(ValueError, match="min_similarity"):
            filter_by_similarity(sample_html_diff_report, 80.0, 20.0)


class TestFilterByChangeType:
    """Tests for filter_by_change_type function."""

    def test_filters_by_type(self) -> None:
        """Test filtering returns only matching change types."""
        changes = [
            HTMLChange(change_type="text_change", description="d"),
            HTMLChange(change_type="structure_change", description="d"),
            HTMLChange(change_type="metadata_change", description="d"),
        ]
        result = HTMLDiffResult(
            old_path="a.html",
            new_path="b.html",
            old_topic_slug="t",
            new_topic_slug="t",
            relationship="modified",
            changes=changes,
            text_similarity=50.0,
            has_structural_changes=True,
        )
        filtered = filter_by_change_type(result, {"text_change", "metadata_change"})
        assert len(filtered) == 2


class TestGetPrimaryText:
    """Tests for get_primary_text function."""

    def test_prefers_new_text(self) -> None:
        """Test new_text is preferred over old_text."""
        change = HTMLChange(
            change_type="text_change",
            description="d",
            old_text="old",
            new_text="new",
        )
        assert get_primary_text(change) == "new"

    def test_falls_back_to_old(self) -> None:
        """Test old_text is returned when new_text is None."""
        change = HTMLChange(
            change_type="text_change",
            description="d",
            old_text="old",
            new_text=None,
        )
        assert get_primary_text(change) == "old"

    def test_returns_none_if_both_absent(self) -> None:
        """Test None is returned when both texts are absent."""
        change = HTMLChange(
            change_type="text_change",
            description="d",
        )
        assert get_primary_text(change) is None


class TestCountTextChanges:
    """Tests for count_text_changes function."""

    def test_counts_across_results(self) -> None:
        """Test counting text changes across multiple results."""
        result1 = HTMLDiffResult(
            old_path="a.html",
            new_path="b.html",
            old_topic_slug="t",
            new_topic_slug="t",
            relationship="modified",
            changes=[
                HTMLChange(change_type="text_change", description="d", new_text="a"),
                HTMLChange(change_type="text_change", description="d", new_text="b"),
            ],
            text_similarity=50.0,
            has_structural_changes=False,
        )
        result2 = HTMLDiffResult(
            old_path="c.html",
            new_path="d.html",
            old_topic_slug="t2",
            new_topic_slug="t2",
            relationship="modified",
            changes=[
                HTMLChange(change_type="text_change", description="d", old_text="c"),
            ],
            text_similarity=60.0,
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
        assert count_text_changes(report) == 3

    def test_empty_report(self) -> None:
        """Test empty report returns zero count."""
        report = HTMLDiffReport(
            old_version="1",
            new_version="2",
            old_root="/old",
            new_root="/new",
            results=[],
            total_compared=0,
            total_with_changes=0,
        )
        assert count_text_changes(report) == 0
