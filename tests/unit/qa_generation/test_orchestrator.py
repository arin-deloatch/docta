# pylint: disable=redefined-outer-name,too-many-positional-arguments
"""Unit tests for qa_generation.pipeline.orchestrator module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from qa_generation.models import GeneratorConfig, QAPair, QASourceDocument
from qa_generation.pipeline.orchestrator import (
    _generate_stratified_by_topic,
    generate_qa_from_both_sources,
    generate_qa_from_delta_report,
    generate_qa_from_report,
)


@pytest.fixture
def mock_qa_pairs() -> list[QAPair]:
    """Provide a list of mock QA pairs for orchestrator tests."""
    return [
        QAPair(
            question="What is foo?",
            ground_truth_answer="Foo is bar.",
            source_topic_slug="guide",
        ),
    ]


@pytest.fixture
def source_docs_multi_topic() -> list[QASourceDocument]:
    """Provide source documents spanning multiple topics."""
    return [
        QASourceDocument(
            content="Content about installation guide for topic A",
            topic_slug="topic-a",
        ),
        QASourceDocument(
            content="Content about configuration for topic A",
            topic_slug="topic-a",
        ),
        QASourceDocument(
            content="Content about deployment for topic B",
            topic_slug="topic-b",
        ),
    ]


class TestGenerateStratifiedByTopic:
    """Tests for _generate_stratified_by_topic function."""

    def test_distributes_across_topics(
        self,
        source_docs_multi_topic: list[QASourceDocument],
        sample_generator_config: GeneratorConfig,
        mock_qa_pairs: list[QAPair],
    ) -> None:
        """Test QA generation is distributed across multiple topics."""
        mock_generator = MagicMock()
        mock_generator.generate.return_value = mock_qa_pairs

        result = _generate_stratified_by_topic(
            source_docs_multi_topic,
            mock_generator,
            sample_generator_config,
            total_testset_size=10,
        )
        assert len(result) == 2
        assert mock_generator.generate.call_count == 2

    def test_handles_topic_generation_failure(
        self,
        source_docs_multi_topic: list[QASourceDocument],
        sample_generator_config: GeneratorConfig,
        mock_qa_pairs: list[QAPair],
    ) -> None:
        """Test partial topic failure still returns results from other topics."""
        mock_generator = MagicMock()
        mock_generator.generate.side_effect = [
            Exception("API error"),
            mock_qa_pairs,
        ]

        result = _generate_stratified_by_topic(
            source_docs_multi_topic,
            mock_generator,
            sample_generator_config,
            total_testset_size=10,
        )
        assert len(result) == 1

    def test_all_topics_fail_raises(
        self,
        source_docs_multi_topic: list[QASourceDocument],
        sample_generator_config: GeneratorConfig,
    ) -> None:
        """Test all topics failing raises RuntimeError."""
        mock_generator = MagicMock()
        mock_generator.generate.side_effect = Exception("total failure")

        with pytest.raises(RuntimeError, match="no QA pairs generated"):
            _generate_stratified_by_topic(
                source_docs_multi_topic,
                mock_generator,
                sample_generator_config,
                total_testset_size=10,
            )

    def test_remainder_distribution(
        self,
        sample_generator_config: GeneratorConfig,
        mock_qa_pairs: list[QAPair],
    ) -> None:
        """Test testset_size remainder is distributed across topics."""
        docs = [
            QASourceDocument(content="Topic A content", topic_slug="a"),
            QASourceDocument(content="Topic B content", topic_slug="b"),
            QASourceDocument(content="Topic C content", topic_slug="c"),
        ]
        mock_generator = MagicMock()
        mock_generator.generate.return_value = mock_qa_pairs

        _generate_stratified_by_topic(docs, mock_generator, sample_generator_config, total_testset_size=10)
        calls = mock_generator.generate.call_args_list
        quotas = [call.args[1].testset_size for call in calls]
        assert sum(quotas) == 10


class TestGenerateQaFromReport:
    """Tests for generate_qa_from_report function."""

    @patch("qa_generation.pipeline.orchestrator.write_qa_pairs")
    @patch("qa_generation.pipeline.orchestrator.RAGASQAGenerator")
    @patch("qa_generation.pipeline.orchestrator.extract_snippets")
    @patch("qa_generation.pipeline.orchestrator.read_diff_report")
    def test_basic_pipeline(
        self,
        mock_read: MagicMock,
        mock_extract: MagicMock,
        mock_generator_class: MagicMock,
        mock_write: MagicMock,
        mock_qa_pairs: list[QAPair],
        tmp_path: Path,
    ) -> None:
        """Test basic end-to-end pipeline from diff report to QA pairs."""
        mock_report = MagicMock()
        mock_report.results = [MagicMock()]
        mock_read.return_value = mock_report

        source_doc = QASourceDocument(content="Test content", topic_slug="guide")
        mock_stats = MagicMock()
        mock_stats.extracted_snippets = 1
        mock_stats.total_filtered = 0
        mock_stats.extraction_rate = 100.0
        mock_extract.return_value = ([source_doc], mock_stats)

        mock_generator = MagicMock()
        mock_generator.generate.return_value = mock_qa_pairs
        mock_generator_class.return_value = mock_generator

        settings = MagicMock()
        settings.testset_size = 10
        settings.to_generator_config.return_value = GeneratorConfig(testset_size=10)

        output = tmp_path / "output.json"
        result = generate_qa_from_report(
            report_path=tmp_path / "report.json",
            output_path=output,
            settings=settings,
        )
        assert len(result) == 1
        settings.setup_environment.assert_called_once()
        mock_write.assert_called_once()

    @patch("qa_generation.pipeline.orchestrator.extract_snippets")
    @patch("qa_generation.pipeline.orchestrator.read_diff_report")
    def test_no_snippets_raises(
        self,
        mock_read: MagicMock,
        mock_extract: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test no extracted snippets raises ValueError."""
        mock_report = MagicMock()
        mock_report.results = []
        mock_read.return_value = mock_report

        mock_stats = MagicMock()
        mock_stats.extracted_snippets = 0
        mock_stats.total_filtered = 5
        mock_stats.total_changes = 5
        mock_stats.extraction_rate = 0.0
        mock_extract.return_value = ([], mock_stats)

        settings = MagicMock()
        settings.testset_size = 10
        settings.to_generator_config.return_value = GeneratorConfig(testset_size=10)

        with pytest.raises(ValueError, match="No snippets extracted"):
            generate_qa_from_report(
                report_path=tmp_path / "report.json",
                output_path=tmp_path / "output.json",
                settings=settings,
            )

    @patch("qa_generation.pipeline.orchestrator.write_qa_pairs")
    @patch("qa_generation.pipeline.orchestrator.RAGASQAGenerator")
    @patch("qa_generation.pipeline.orchestrator.extract_snippets")
    @patch("qa_generation.pipeline.orchestrator.read_diff_report")
    def test_multi_topic_uses_stratified(
        self,
        mock_read: MagicMock,
        mock_extract: MagicMock,
        mock_generator_class: MagicMock,
        _mock_write: MagicMock,
        mock_qa_pairs: list[QAPair],
        tmp_path: Path,
    ) -> None:
        """Test multiple topics trigger stratified generation."""
        mock_read.return_value = MagicMock(results=[MagicMock()])

        source_docs = [
            QASourceDocument(content="Topic A content", topic_slug="a"),
            QASourceDocument(content="Topic B content", topic_slug="b"),
        ]
        mock_stats = MagicMock()
        mock_stats.extracted_snippets = 2
        mock_stats.total_filtered = 0
        mock_stats.extraction_rate = 100.0
        mock_extract.return_value = (source_docs, mock_stats)

        mock_generator = MagicMock()
        mock_generator.generate.return_value = mock_qa_pairs
        mock_generator_class.return_value = mock_generator

        settings = MagicMock()
        settings.testset_size = 10
        settings.to_generator_config.return_value = GeneratorConfig(testset_size=10)

        generate_qa_from_report(
            report_path=tmp_path / "report.json",
            output_path=tmp_path / "output.json",
            settings=settings,
        )
        assert mock_generator.generate.call_count == 2


class TestGenerateQaFromDeltaReport:
    """Tests for generate_qa_from_delta_report function."""

    @patch("qa_generation.pipeline.orchestrator.write_qa_pairs")
    @patch("qa_generation.pipeline.orchestrator.RAGASQAGenerator")
    @patch("qa_generation.pipeline.orchestrator.convert_added_documents")
    @patch("qa_generation.pipeline.orchestrator.extract_added_documents")
    @patch("qa_generation.pipeline.orchestrator.read_delta_report")
    def test_basic_pipeline(
        self,
        mock_read: MagicMock,
        mock_extract: MagicMock,
        mock_convert: MagicMock,
        mock_generator_class: MagicMock,
        _mock_write: MagicMock,
        mock_qa_pairs: list[QAPair],
        tmp_path: Path,
    ) -> None:
        """Test basic pipeline from delta report to QA pairs."""
        mock_delta = MagicMock()
        mock_delta.added = [MagicMock()]
        mock_delta.modified = []
        mock_delta.renamed_candidates = []
        mock_read.return_value = mock_delta

        mock_extract.return_value = [MagicMock()]
        source_doc = QASourceDocument(content="Added doc content", topic_slug="new-guide")
        mock_convert.return_value = [source_doc]

        mock_generator = MagicMock()
        mock_generator.generate.return_value = mock_qa_pairs
        mock_generator_class.return_value = mock_generator

        settings = MagicMock()
        settings.testset_size = 10
        settings.to_generator_config.return_value = GeneratorConfig(testset_size=10)

        result = generate_qa_from_delta_report(
            delta_report_path=tmp_path / "delta.json",
            output_path=tmp_path / "output.json",
            settings=settings,
        )
        assert len(result) == 1
        settings.setup_environment.assert_called_once()

    @patch("qa_generation.pipeline.orchestrator.read_delta_report")
    def test_no_added_docs_raises(
        self,
        mock_read: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test no added documents raises ValueError."""
        mock_delta = MagicMock()
        mock_delta.added = []
        mock_delta.modified = [MagicMock()]
        mock_delta.renamed_candidates = []
        mock_read.return_value = mock_delta

        settings = MagicMock()
        settings.testset_size = 10

        with pytest.raises(ValueError, match="No added documents"):
            generate_qa_from_delta_report(
                delta_report_path=tmp_path / "delta.json",
                output_path=tmp_path / "output.json",
                settings=settings,
            )

    @patch("qa_generation.pipeline.orchestrator.convert_added_documents")
    @patch("qa_generation.pipeline.orchestrator.extract_added_documents")
    @patch("qa_generation.pipeline.orchestrator.read_delta_report")
    def test_no_source_docs_raises(
        self,
        mock_read: MagicMock,
        mock_extract: MagicMock,
        mock_convert: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test no source documents after conversion raises ValueError."""
        mock_delta = MagicMock()
        mock_delta.added = [MagicMock()]
        mock_read.return_value = mock_delta

        mock_extract.return_value = [MagicMock()]
        mock_convert.return_value = []

        settings = MagicMock()
        settings.testset_size = 10
        settings.to_generator_config.return_value = GeneratorConfig(testset_size=10)

        with pytest.raises(ValueError, match="No source documents"):
            generate_qa_from_delta_report(
                delta_report_path=tmp_path / "delta.json",
                output_path=tmp_path / "output.json",
                settings=settings,
            )


class TestGenerateQaFromBothSources:
    """Tests for generate_qa_from_both_sources function."""

    @patch("qa_generation.pipeline.orchestrator.write_qa_pairs")
    @patch("qa_generation.pipeline.orchestrator.RAGASQAGenerator")
    @patch("qa_generation.pipeline.orchestrator.convert_added_documents")
    @patch("qa_generation.pipeline.orchestrator.extract_added_documents")
    @patch("qa_generation.pipeline.orchestrator.read_delta_report")
    @patch("qa_generation.pipeline.orchestrator.extract_snippets")
    @patch("qa_generation.pipeline.orchestrator.read_diff_report")
    def test_merges_both_sources(
        self,
        mock_read_diff: MagicMock,
        mock_extract_snippets: MagicMock,
        mock_read_delta: MagicMock,
        mock_extract_added: MagicMock,
        mock_convert: MagicMock,
        mock_generator_class: MagicMock,
        _mock_write: MagicMock,
        mock_qa_pairs: list[QAPair],
        tmp_path: Path,
    ) -> None:
        """Test merging diff and delta sources produces combined QA pairs."""
        mock_diff_report = MagicMock()
        mock_diff_report.results = [MagicMock()]
        mock_read_diff.return_value = mock_diff_report

        modified_doc = QASourceDocument(content="Modified content", topic_slug="modified")
        mock_stats = MagicMock()
        mock_stats.extracted_snippets = 1
        mock_stats.extraction_rate = 100.0
        mock_extract_snippets.return_value = ([modified_doc], mock_stats)

        mock_delta = MagicMock()
        mock_delta.added = [MagicMock()]
        mock_read_delta.return_value = mock_delta

        mock_extract_added.return_value = [MagicMock()]
        added_doc = QASourceDocument(content="Added content", topic_slug="added")
        mock_convert.return_value = [added_doc]

        mock_generator = MagicMock()
        mock_generator.generate.return_value = mock_qa_pairs
        mock_generator_class.return_value = mock_generator

        settings = MagicMock()
        settings.testset_size = 10
        settings.to_generator_config.return_value = GeneratorConfig(testset_size=10)

        result = generate_qa_from_both_sources(
            delta_report_path=tmp_path / "delta.json",
            semantic_diff_report_path=tmp_path / "diff.json",
            output_path=tmp_path / "output.json",
            settings=settings,
        )
        assert len(result) >= 1
        assert mock_generator.generate.call_count == 2

    @patch("qa_generation.pipeline.orchestrator.read_delta_report")
    @patch("qa_generation.pipeline.orchestrator.extract_snippets")
    @patch("qa_generation.pipeline.orchestrator.read_diff_report")
    def test_no_sources_raises(
        self,
        mock_read_diff: MagicMock,
        mock_extract_snippets: MagicMock,
        mock_read_delta: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test no sources after merging raises ValueError."""
        mock_read_diff.return_value = MagicMock(results=[])
        mock_stats = MagicMock()
        mock_stats.extracted_snippets = 0
        mock_stats.extraction_rate = 0.0
        mock_extract_snippets.return_value = ([], mock_stats)

        mock_delta = MagicMock()
        mock_delta.added = []
        mock_read_delta.return_value = mock_delta

        settings = MagicMock()
        settings.testset_size = 10
        settings.to_generator_config.return_value = GeneratorConfig(testset_size=10)

        with pytest.raises(ValueError, match="No source documents after merging"):
            generate_qa_from_both_sources(
                delta_report_path=tmp_path / "delta.json",
                semantic_diff_report_path=tmp_path / "diff.json",
                output_path=tmp_path / "output.json",
                settings=settings,
            )

    @patch("qa_generation.pipeline.orchestrator.write_qa_pairs")
    @patch("qa_generation.pipeline.orchestrator.RAGASQAGenerator")
    @patch("qa_generation.pipeline.orchestrator.read_delta_report")
    @patch("qa_generation.pipeline.orchestrator.extract_snippets")
    @patch("qa_generation.pipeline.orchestrator.read_diff_report")
    def test_num_documents_limits_sources(
        self,
        mock_read_diff: MagicMock,
        mock_extract_snippets: MagicMock,
        mock_read_delta: MagicMock,
        mock_generator_class: MagicMock,
        _mock_write: MagicMock,
        mock_qa_pairs: list[QAPair],
        tmp_path: Path,
    ) -> None:
        """Test num_documents parameter limits source document count."""
        mock_read_diff.return_value = MagicMock(results=[])

        source_docs = [QASourceDocument(content=f"doc {i}", topic_slug="t") for i in range(10)]
        mock_stats = MagicMock()
        mock_stats.extracted_snippets = 10
        mock_stats.extraction_rate = 100.0
        mock_extract_snippets.return_value = (source_docs, mock_stats)

        mock_delta = MagicMock()
        mock_delta.added = []
        mock_read_delta.return_value = mock_delta

        mock_generator = MagicMock()
        mock_generator.generate.return_value = mock_qa_pairs
        mock_generator_class.return_value = mock_generator

        settings = MagicMock()
        settings.testset_size = 10
        settings.to_generator_config.return_value = GeneratorConfig(testset_size=10)

        generate_qa_from_both_sources(
            delta_report_path=tmp_path / "delta.json",
            semantic_diff_report_path=tmp_path / "diff.json",
            output_path=tmp_path / "output.json",
            settings=settings,
            num_documents=3,
        )
        call_args = mock_generator.generate.call_args
        assert len(call_args.args[0]) == 3
