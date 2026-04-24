# pylint: disable=redefined-outer-name
"""Shared fixtures for qa_generation tests."""

from __future__ import annotations

from typing import Any

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


@pytest.fixture
def sample_html_change() -> HTMLChange:
    """Provide a sample HTMLChange with text content."""
    return HTMLChange(
        change_type="text_change",
        description="Updated installation instructions",
        old_text="Install with pip install foo",
        new_text="Install with uv add foo",
        location="Installation > Quick Start",
    )


@pytest.fixture
def sample_html_change_no_text() -> HTMLChange:
    """Provide a sample HTMLChange without text content."""
    return HTMLChange(
        change_type="structure_change",
        description="Reorganized headings",
        old_text=None,
        new_text=None,
        location="Overview",
    )


@pytest.fixture
def sample_html_diff_result(sample_html_change: HTMLChange) -> HTMLDiffResult:
    """Provide a sample HTMLDiffResult containing one change."""
    return HTMLDiffResult(
        old_path="/docs/v1/guide.html",
        new_path="/docs/v2/guide.html",
        old_topic_slug="guide",
        new_topic_slug="guide",
        relationship="modified",
        changes=[sample_html_change],
        text_similarity=75.0,
        has_structural_changes=False,
    )


@pytest.fixture
def sample_html_diff_report(sample_html_diff_result: HTMLDiffResult) -> HTMLDiffReport:
    """Provide a sample HTMLDiffReport with one result."""
    return HTMLDiffReport(
        old_version="1.0.0",
        new_version="2.0.0",
        old_root="/docs/v1",
        new_root="/docs/v2",
        results=[sample_html_diff_result],
        total_compared=1,
        total_with_changes=1,
    )


@pytest.fixture
def sample_filter_config() -> FilterConfig:
    """Provide a sample FilterConfig with custom thresholds."""
    return FilterConfig(
        min_text_length=10,
        max_text_length=5000,
        change_types={"text_change"},
        min_similarity=0.0,
        max_similarity=95.0,
    )


@pytest.fixture
def sample_generator_config() -> GeneratorConfig:
    """Provide a sample GeneratorConfig with default query distribution."""
    return GeneratorConfig(
        testset_size=10,
        query_distribution=QueryDistribution(
            specific=0.5,
            abstract=0.25,
            comparative=0.25,
        ),
        filtering=FilterConfig(),
        llm=LLMConfig(),
        embedding=EmbeddingConfig(),
    )


@pytest.fixture
def sample_qa_source_document() -> QASourceDocument:
    """Provide a sample QASourceDocument with metadata."""
    return QASourceDocument(
        content="Install with uv add foo. This is the recommended installation method.",
        topic_slug="guide",
        location="Installation > Quick Start",
        change_type="text_change",
        metadata={
            "versions": {"old": "1.0.0", "new": "2.0.0"},
            "change_description": "Updated installation instructions",
        },
    )


@pytest.fixture
def sample_qa_pair() -> QAPair:
    """Provide a sample QAPair with full traceability fields."""
    return QAPair(
        question="How do you install foo?",
        ground_truth_answer="Install with uv add foo.",
        source_topic_slug="guide",
        source_location="Installation > Quick Start",
        source_change_type="text_change",
        source_versions=("1.0.0", "2.0.0"),
        question_type="specific",
        metadata={"generated_at": "2026-01-01T00:00:00+00:00"},
    )


@pytest.fixture
def sample_source_document_info() -> SourceDocumentInfo:
    """Provide a sample SourceDocumentInfo with version metadata."""
    return SourceDocumentInfo(
        topic_slug="guide",
        location="Installation > Quick Start",
        change_type="text_change",
        versions=("1.0.0", "2.0.0"),
        metadata={"change_description": "Updated installation instructions"},
    )


@pytest.fixture
def sample_snippet_stats() -> SnippetExtractionStats:
    """Provide a default SnippetExtractionStats instance."""
    return SnippetExtractionStats()


@pytest.fixture
def sample_added_doc_stats() -> AddedDocumentStats:
    """Provide a default AddedDocumentStats instance."""
    return AddedDocumentStats()


@pytest.fixture
def sample_document_record() -> DocumentRecord:
    """Provide a sample DocumentRecord for an added document."""
    return DocumentRecord(
        version="2.0.0",
        root="/docs/v2",
        relative_path="new_guide.html",
        topic_slug="new-guide",
        html_filename="new_guide.html",
        raw_hash="abc123",
    )


@pytest.fixture
def sample_delta_report(sample_document_record: DocumentRecord) -> DeltaReport:
    """Provide a sample DeltaReport with one added document."""
    return DeltaReport(
        old_version="1.0.0",
        new_version="2.0.0",
        unchanged=[],
        modified=[],
        renamed_candidates=[],
        removed=[],
        added=[sample_document_record],
    )


@pytest.fixture
def sample_heading() -> Heading:
    """Provide a sample level-2 Heading."""
    return Heading(
        text="Installation",
        level=2,
        html_snippet="<h2>Installation</h2>",
    )


@pytest.fixture
def sample_text_block() -> TextBlock:
    """Provide a sample paragraph TextBlock."""
    return TextBlock(
        block_type="paragraph",
        text="Install the package using pip.",
        html_snippet="<p>Install the package using pip.</p>",
        char_count=30,
        word_count=5,
    )


@pytest.fixture
def sample_code_block() -> CodeBlock:
    """Provide a sample bash CodeBlock."""
    return CodeBlock(
        code="pip install foo",
        language="bash",
        is_inline=False,
        html_snippet="<pre><code>pip install foo</code></pre>",
        line_count=1,
    )


@pytest.fixture
def sample_section(
    sample_heading: Heading,
    sample_text_block: TextBlock,
    sample_code_block: CodeBlock,
) -> Section:
    """Provide a sample Section with heading, text, and code blocks."""
    return Section(
        heading=sample_heading,
        text_blocks=[sample_text_block],
        code_blocks=[sample_code_block],
    )


@pytest.fixture
def sample_extracted_document(sample_section: Section) -> ExtractedDocument:
    """Provide a sample ExtractedDocument with one section."""
    return ExtractedDocument(
        metadata=DocumentMetadata(title="Guide"),
        sections=[sample_section],
        source_path="/docs/v2/new_guide.html",
        full_text="Installation\nInstall the package using pip.\npip install foo",
        total_char_count=50,
        total_word_count=8,
    )


@pytest.fixture
def sample_qa_settings_dict() -> dict[str, Any]:
    """Settings dict that bypasses env var loading for tests."""
    return {
        "testset_size": 10,
        "llm_provider": "openai",
        "llm_model": "gpt-4o",
        "llm_temperature": 0.3,
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "query_dist_specific": 0.5,
        "query_dist_abstract": 0.25,
        "query_dist_comparative": 0.25,
        "filter_min_text_length": 50,
        "filter_max_text_length": 10000,
        "filter_min_similarity": 0.0,
        "filter_max_similarity": 95.0,
    }
