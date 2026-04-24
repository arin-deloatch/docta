# pylint: disable=protected-access,too-many-public-methods
"""Unit tests for qa_generation.generators module."""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest

from qa_generation.generators.base import (
    ConfigurationError,
    LLMError,
    QAGenerationError,
    QAGenerator,
)
from qa_generation.generators.ragas_generator import RAGASQAGenerator
from qa_generation.models import (
    GeneratorConfig,
    QAPair,
    QASourceDocument,
    SourceDocumentInfo,
)

# --- base.py ---


class TestQAGeneratorProtocol:
    """Tests for QAGenerator protocol and exception hierarchy."""

    def test_exception_hierarchy(self) -> None:
        """Test exception classes form correct inheritance chain."""
        assert issubclass(QAGenerationError, RuntimeError)
        assert issubclass(LLMError, QAGenerationError)
        assert issubclass(ConfigurationError, QAGenerationError)

    def test_protocol_is_runtime_checkable(self) -> None:
        """Test compliant class passes runtime protocol check."""

        class FakeGenerator:
            """Fake generator implementing the QAGenerator protocol."""

            def generate(
                self,
                _documents: list[QASourceDocument],
                _config: GeneratorConfig,
            ) -> list[QAPair]:
                """Generate empty list for testing."""
                return []

        gen = FakeGenerator()
        assert isinstance(gen, QAGenerator)

    def test_non_compliant_class_fails_check(self) -> None:
        """Test non-compliant class fails runtime protocol check."""

        class NotAGenerator:
            """Non-compliant class without generate method."""

        assert not isinstance(NotAGenerator(), QAGenerator)


# --- ragas_generator.py ---


class TestRAGASQAGenerator:
    """Tests for RAGASQAGenerator class."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Provide mock QAGenerationSettings."""
        settings = MagicMock()
        settings.llm_provider = "openai"
        settings.llm_model = "gpt-4o"
        settings.embedding_provider = "openai"
        settings.embedding_model = "text-embedding-3-small"
        return settings

    @pytest.fixture
    def generator(self, mock_settings: MagicMock) -> RAGASQAGenerator:
        """Provide a RAGASQAGenerator instance with mock settings."""
        return RAGASQAGenerator(mock_settings)

    def test_init(self, mock_settings: MagicMock) -> None:
        """Test generator initializes with settings and no cached generator."""
        gen = RAGASQAGenerator(mock_settings)
        assert gen.settings is mock_settings
        assert gen._generator is None

    def test_generate_empty_documents_raises(
        self,
        generator: RAGASQAGenerator,
        sample_generator_config: GeneratorConfig,
    ) -> None:
        """Test empty document list raises ValueError."""
        with pytest.raises(ValueError, match="Documents list cannot be empty"):
            generator.generate([], sample_generator_config)

    @patch("qa_generation.generators.ragas_generator.create_testset_generator")
    def test_ensure_generator_creates_once(
        self,
        mock_create: MagicMock,
        generator: RAGASQAGenerator,
    ) -> None:
        """Test generator is created only once and cached."""
        mock_tsg = MagicMock()
        mock_create.return_value = mock_tsg

        result1 = generator._ensure_generator()
        result2 = generator._ensure_generator()
        assert result1 is result2
        mock_create.assert_called_once()

    @patch("qa_generation.generators.ragas_generator.create_testset_generator")
    def test_ensure_generator_value_error_raises_config_error(
        self,
        mock_create: MagicMock,
        generator: RAGASQAGenerator,
    ) -> None:
        """Test ValueError during creation raises ConfigurationError."""
        mock_create.side_effect = ValueError("bad config")
        with pytest.raises(ConfigurationError, match="Invalid configuration"):
            generator._ensure_generator()

    @patch("qa_generation.generators.ragas_generator.create_testset_generator")
    def test_ensure_generator_import_error_raises_config_error(
        self,
        mock_create: MagicMock,
        generator: RAGASQAGenerator,
    ) -> None:
        """Test ImportError during creation raises ConfigurationError."""
        mock_create.side_effect = ImportError("missing ragas")
        with pytest.raises(ConfigurationError, match="Missing dependencies"):
            generator._ensure_generator()

    def test_extract_versions_valid(self, generator: RAGASQAGenerator) -> None:
        """Test extracting valid version tuple from metadata."""
        metadata = {"versions": {"old": "1.0", "new": "2.0"}}
        result = generator._extract_versions(metadata)
        assert result == ("1.0", "2.0")

    def test_extract_versions_missing_key(self, generator: RAGASQAGenerator) -> None:
        """Test missing versions key returns None."""
        assert generator._extract_versions({}) is None

    def test_extract_versions_not_dict(self, generator: RAGASQAGenerator) -> None:
        """Test non-dict versions value returns None."""
        assert generator._extract_versions({"versions": "1.0"}) is None

    def test_extract_versions_incomplete(self, generator: RAGASQAGenerator) -> None:
        """Test incomplete versions dict returns None."""
        assert generator._extract_versions({"versions": {"old": "1.0"}}) is None

    def test_convert_to_ragas_documents(self, generator: RAGASQAGenerator) -> None:
        """Test conversion to RAGAS document format with DOC_ID markers."""
        docs = [
            QASourceDocument(
                content="Test content",
                topic_slug="test",
                location="Section A",
                change_type="text_change",
            ),
        ]
        ragas_docs = generator._convert_to_ragas_documents(docs)
        assert len(ragas_docs) == 1
        assert "<!--DOC_ID:0-->" in ragas_docs[0].page_content
        assert "Test content" in ragas_docs[0].page_content
        assert ragas_docs[0].metadata["topic_slug"] == "test"

    def test_build_qa_pair(self, generator: RAGASQAGenerator) -> None:
        """Test building QAPair from RAGAS row and source info."""
        row = {
            "user_input": "What is foo?",
            "reference": "Foo is a bar.",
            "synthesizer_name": "specific",
        }
        source_info = SourceDocumentInfo(
            topic_slug="guide",
            location="Section A",
            change_type="text_change",
            versions=("1.0", "2.0"),
            metadata={},
        )
        qa = generator._build_qa_pair(row, source_info)
        assert qa.question == "What is foo?"
        assert qa.ground_truth_answer == "Foo is a bar."
        assert qa.source_topic_slug == "guide"
        assert qa.question_type == "specific"
        assert "generated_at" in qa.metadata

    def test_build_qa_pair_with_content_metadata(self, generator: RAGASQAGenerator) -> None:
        """Test build_qa_pair includes content metadata fields."""
        row = {"user_input": "Q?", "reference": "A."}
        source_info = SourceDocumentInfo(
            topic_slug="t",
            metadata={
                "change_description": "Updated text",
                "old_content": "old",
                "new_content": "new",
            },
        )
        qa = generator._build_qa_pair(row, source_info)
        assert qa.metadata["change_description"] == "Updated text"
        assert qa.metadata["old_content"] == "old"
        assert qa.metadata["new_content"] == "new"

    def test_extract_from_doc_id_markers_found(self, generator: RAGASQAGenerator) -> None:
        """Test DOC_ID marker extraction finds matching document."""
        doc = QASourceDocument(content="content", topic_slug="guide")
        id_to_doc = {0: doc}
        pattern = re.compile(r"<!--DOC_ID:(\d+)-->")
        row = {"contexts": ["<!--DOC_ID:0-->Some context text"]}

        result = generator._extract_from_doc_id_markers(row, pattern, id_to_doc)
        assert result is not None
        assert result.topic_slug == "guide"

    def test_extract_from_doc_id_markers_not_found(self, generator: RAGASQAGenerator) -> None:
        """Test DOC_ID marker extraction returns None when no marker found."""
        pattern = re.compile(r"<!--DOC_ID:(\d+)-->")
        row = {"contexts": ["No marker here"]}

        result = generator._extract_from_doc_id_markers(row, pattern, {})
        assert result is None

    def test_extract_from_doc_id_markers_string_context(self, generator: RAGASQAGenerator) -> None:
        """Test DOC_ID marker extraction from string reference field."""
        doc = QASourceDocument(content="content", topic_slug="test")
        id_to_doc = {0: doc}
        pattern = re.compile(r"<!--DOC_ID:(\d+)-->")
        row = {"reference": "<!--DOC_ID:0-->answer text"}

        result = generator._extract_from_doc_id_markers(row, pattern, id_to_doc)
        assert result is not None

    def test_match_by_content_found(self, generator: RAGASQAGenerator) -> None:
        """Test content-based matching finds source document."""
        pattern = re.compile(r"<!--DOC_ID:(\d+)-->")
        long_prefix = "A" * 60
        docs = [
            QASourceDocument(
                content=f"{long_prefix} This is the content that should be matched.",
                topic_slug="matched-topic",
            ),
        ]
        ground_truth = f"{long_prefix} This is the content that should be matched. Plus extra answer text."
        result = generator._match_by_content(ground_truth, pattern, docs)
        assert result is not None
        assert result.topic_slug == "matched-topic"

    def test_match_by_content_not_found(self, generator: RAGASQAGenerator) -> None:
        """Test content-based matching returns None when no match."""
        pattern = re.compile(r"<!--DOC_ID:(\d+)-->")
        docs = [QASourceDocument(content="totally different content", topic_slug="t")]
        result = generator._match_by_content("no match here", pattern, docs)
        assert result is None

    def test_match_by_content_short_text_skipped(self, generator: RAGASQAGenerator) -> None:
        """Test short content is skipped during content matching."""
        pattern = re.compile(r"<!--DOC_ID:(\d+)-->")
        docs = [QASourceDocument(content="short", topic_slug="t")]
        result = generator._match_by_content("short", pattern, docs)
        assert result is None

    def test_find_source_document_default_unknown(self, generator: RAGASQAGenerator) -> None:
        """Test unmatched source defaults to unknown topic slug."""
        pattern = re.compile(r"<!--DOC_ID:(\d+)-->")
        row = {"user_input": "question"}
        result = generator._find_source_document(
            row=row,
            ground_truth="",
            doc_id_pattern=pattern,
            id_to_doc={},
            source_documents=[],
        )
        assert result.topic_slug == "unknown"

    @patch("qa_generation.generators.ragas_generator.create_testset_generator")
    def test_generate_full_flow(
        self,
        mock_create: MagicMock,
        generator: RAGASQAGenerator,
        sample_generator_config: GeneratorConfig,
    ) -> None:
        """Test end-to-end QA generation flow with mocked RAGAS."""
        import pandas as pd  # type: ignore[import-untyped]

        mock_testset = MagicMock()
        mock_testset.to_pandas.return_value = pd.DataFrame(
            [
                {
                    "user_input": "What is foo?",
                    "reference": "<!--DOC_ID:0-->\nFoo is a bar.",
                    "synthesizer_name": "specific",
                },
            ]
        )

        mock_tsg = MagicMock()
        mock_tsg.generate_with_langchain_docs.return_value = mock_testset
        mock_tsg.llm = MagicMock()
        mock_create.return_value = mock_tsg

        docs = [
            QASourceDocument(
                content="Foo is a bar. This content explains what foo is.",
                topic_slug="guide",
                location="Section A",
                change_type="text_change",
            ),
        ]

        qa_pairs = generator.generate(docs, sample_generator_config)
        assert len(qa_pairs) == 1
        assert qa_pairs[0].question == "What is foo?"
        assert qa_pairs[0].source_topic_slug == "guide"

    @patch("qa_generation.generators.ragas_generator.create_testset_generator")
    def test_generate_api_error_raises_llm_error(
        self,
        mock_create: MagicMock,
        generator: RAGASQAGenerator,
        sample_generator_config: GeneratorConfig,
    ) -> None:
        """Test API error during generation raises LLMError."""
        mock_tsg = MagicMock()
        mock_tsg.generate_with_langchain_docs.side_effect = Exception("rate limit exceeded 429")
        mock_tsg.llm = MagicMock()
        mock_create.return_value = mock_tsg

        docs = [QASourceDocument(content="Test content here", topic_slug="t")]

        with pytest.raises(LLMError, match="LLM API error"):
            generator.generate(docs, sample_generator_config)

    @patch("qa_generation.generators.ragas_generator.create_testset_generator")
    def test_generate_with_retry_batch_fallback(
        self,
        mock_create: MagicMock,
        generator: RAGASQAGenerator,
        sample_generator_config: GeneratorConfig,
    ) -> None:
        """Test generation retries with batch fallback on parser error."""
        import pandas as pd  # type: ignore[import-untyped]
        from langchain_core.exceptions import OutputParserException

        mock_testset = MagicMock()
        mock_testset.to_pandas.return_value = pd.DataFrame([{"user_input": "Q?", "reference": "A.", "synthesizer_name": "specific"}])

        mock_tsg = MagicMock()
        mock_tsg.generate_with_langchain_docs.side_effect = [
            OutputParserException("bad json"),
            mock_testset,
        ]
        mock_tsg.llm = MagicMock()
        mock_create.return_value = mock_tsg

        docs = [QASourceDocument(content="Test content", topic_slug="t")]
        qa_pairs = generator.generate(docs, sample_generator_config)
        assert len(qa_pairs) == 1

    @patch("qa_generation.generators.ragas_generator.create_testset_generator")
    def test_generate_all_batches_fail_raises(
        self,
        mock_create: MagicMock,
        generator: RAGASQAGenerator,
        sample_generator_config: GeneratorConfig,
    ) -> None:
        """Test all batch failures raise QAGenerationError."""
        from langchain_core.exceptions import OutputParserException

        mock_tsg = MagicMock()
        mock_tsg.generate_with_langchain_docs.side_effect = OutputParserException("bad")
        mock_tsg.llm = MagicMock()
        mock_create.return_value = mock_tsg

        docs = [QASourceDocument(content="Test content", topic_slug="t")]
        with pytest.raises(QAGenerationError, match="Failed to generate any QA pairs"):
            generator.generate(docs, sample_generator_config)

    @patch("qa_generation.generators.ragas_generator.create_testset_generator")
    def test_convert_from_ragas_testset_no_to_pandas(
        self,
        _mock_create: MagicMock,
        generator: RAGASQAGenerator,
    ) -> None:
        """Test testset without to_pandas raises QAGenerationError."""
        testset = MagicMock(spec=[])
        del testset.to_pandas
        with pytest.raises(QAGenerationError, match="to_pandas"):
            generator._convert_from_ragas_testset(testset, [])
