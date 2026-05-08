# pylint: disable=redefined-outer-name
"""Tests for GenerationSummary model and write_generation_summary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from qa_generation.models import (
    EmbeddingConfig,
    FilterConfig,
    GenerationStats,
    GenerationSummary,
    GeneratorConfig,
    LLMConfig,
    QueryDistribution,
    ReportVersions,
    SourceDocumentsSummary,
)
from qa_generation.output import QAWriteError, write_generation_summary


@pytest.fixture
def sample_report_versions() -> ReportVersions:
    """Provide a sample ReportVersions instance."""
    return ReportVersions(old="9", new="10")


@pytest.fixture
def sample_generator_config() -> GeneratorConfig:
    """Provide a sample GeneratorConfig with realistic values."""
    return GeneratorConfig(
        testset_size=300,
        query_distribution=QueryDistribution(specific=0.5, abstract=0.25, comparative=0.25),
        filtering=FilterConfig(),
        llm=LLMConfig(provider="google", model="gemini-2.5-flash", temperature=0.3),
        embedding=EmbeddingConfig(provider="google", model="models/text-embedding-004"),
    )


@pytest.fixture
def sample_source_documents_summary() -> SourceDocumentsSummary:
    """Provide a sample SourceDocumentsSummary instance."""
    return SourceDocumentsSummary(total=42, topics=8)


@pytest.fixture
def all_success_stats() -> GenerationStats:
    """Provide GenerationStats with no failures."""
    return GenerationStats(requested=300, generated=300, failed_topic_slugs=[])


@pytest.fixture
def partial_failure_stats() -> GenerationStats:
    """Provide GenerationStats with one failed topic."""
    return GenerationStats(
        requested=300,
        generated=261,
        failed_topic_slugs=["managing_replication_in_identity_management"],
    )


@pytest.fixture
def all_success_summary(
    sample_report_versions: ReportVersions,
    sample_generator_config: GeneratorConfig,
    sample_source_documents_summary: SourceDocumentsSummary,
    all_success_stats: GenerationStats,
) -> GenerationSummary:
    """Provide a fully-successful GenerationSummary."""
    return GenerationSummary(
        generated_at="2026-05-08T12:00:00+00:00",
        report_versions=sample_report_versions,
        settings=sample_generator_config,
        source_documents=sample_source_documents_summary,
        generation=all_success_stats,
        output_path="output/qa_pairs.json",
    )


@pytest.fixture
def partial_failure_summary(
    sample_report_versions: ReportVersions,
    sample_generator_config: GeneratorConfig,
    sample_source_documents_summary: SourceDocumentsSummary,
    partial_failure_stats: GenerationStats,
) -> GenerationSummary:
    """Provide a GenerationSummary with one failed topic."""
    return GenerationSummary(
        generated_at="2026-05-08T12:00:00+00:00",
        report_versions=sample_report_versions,
        settings=sample_generator_config,
        source_documents=sample_source_documents_summary,
        generation=partial_failure_stats,
        output_path="output/qa_pairs.json",
    )


class TestGenerationStats:
    """Tests for GenerationStats model."""

    def test_all_success(self, all_success_stats: GenerationStats) -> None:
        """Test that a fully successful run has zero failed topics."""
        assert all_success_stats.failed_topics == 0
        assert all_success_stats.failed_topic_slugs == []
        assert all_success_stats.generated == 300

    def test_partial_failure(self, partial_failure_stats: GenerationStats) -> None:
        """Test that failed_topics reflects the number of failed slugs."""
        assert partial_failure_stats.failed_topics == 1
        assert partial_failure_stats.failed_topic_slugs == ["managing_replication_in_identity_management"]
        assert partial_failure_stats.generated == 261

    def test_failed_topics_derived_from_slugs(self) -> None:
        """Test that failed_topics equals len(failed_topic_slugs)."""
        stats = GenerationStats(requested=100, generated=80, failed_topic_slugs=["topic_a", "topic_b"])
        assert stats.failed_topics == 2
        assert stats.failed_topics == len(stats.failed_topic_slugs)

    def test_failed_topics_in_serialized_output(self) -> None:
        """Test that failed_topics is present in JSON-mode serialization."""
        stats = GenerationStats(requested=100, generated=80, failed_topic_slugs=["topic_a"])
        dumped = stats.model_dump(mode="json")
        assert dumped["failed_topics"] == 1

    def test_non_negative_constraints(self) -> None:
        """Test that negative requested value raises a validation error."""
        with pytest.raises(ValidationError):
            GenerationStats(requested=-1, generated=0, failed_topic_slugs=[])


class TestGenerationSummary:
    """Tests for GenerationSummary model."""

    def test_all_success_summary(self, all_success_summary: GenerationSummary) -> None:
        """Test fields on a fully successful summary."""
        assert all_success_summary.generation.failed_topics == 0
        assert all_success_summary.generation.failed_topic_slugs == []
        assert all_success_summary.generation.generated == 300
        assert all_success_summary.report_versions.old == "9"
        assert all_success_summary.report_versions.new == "10"

    def test_partial_failure_summary(self, partial_failure_summary: GenerationSummary) -> None:
        """Test fields on a summary with one failed topic."""
        assert partial_failure_summary.generation.failed_topics == 1
        assert "managing_replication_in_identity_management" in partial_failure_summary.generation.failed_topic_slugs
        assert partial_failure_summary.generation.generated == 261

    def test_model_serialization_roundtrip(self, all_success_summary: GenerationSummary) -> None:
        """Test that model survives a dump/validate roundtrip without data loss."""
        dumped = all_success_summary.model_dump(mode="python")
        restored = GenerationSummary.model_validate(dumped)
        assert restored.generation.failed_topics == all_success_summary.generation.failed_topics
        assert restored.report_versions.old == all_success_summary.report_versions.old
        assert restored.settings.testset_size == all_success_summary.settings.testset_size

    def test_json_serializable(self, all_success_summary: GenerationSummary) -> None:
        """Test that model serializes to valid JSON without error."""
        # mode="json" converts set fields (e.g. FilterConfig.change_types) to lists
        dumped = all_success_summary.model_dump(mode="json")
        serialized = json.dumps(dumped)
        parsed = json.loads(serialized)
        assert parsed["generation"]["failed_topics"] == 0
        assert parsed["report_versions"]["old"] == "9"

    def test_settings_embeds_generator_config(self, all_success_summary: GenerationSummary) -> None:
        """Test that settings field correctly embeds the full GeneratorConfig."""
        assert all_success_summary.settings.testset_size == 300
        assert all_success_summary.settings.llm.model == "gemini-2.5-flash"
        assert all_success_summary.settings.llm.provider == "google"


class TestWriteGenerationSummary:
    """Tests for write_generation_summary function."""

    def test_writes_json_file(self, tmp_path: Path, all_success_summary: GenerationSummary) -> None:
        """Test that the function writes a well-formed JSON file."""
        output = tmp_path / "generation_summary.json"
        write_generation_summary(all_success_summary, output)

        assert output.exists()
        data = json.loads(output.read_text())
        assert data["generation"]["failed_topics"] == 0
        assert data["generation"]["failed_topic_slugs"] == []
        assert data["report_versions"]["old"] == "9"
        assert data["report_versions"]["new"] == "10"
        assert data["source_documents"]["total"] == 42
        assert data["source_documents"]["topics"] == 8
        assert "generated_at" in data
        assert "output_path" in data

    def test_partial_failure_written_correctly(self, tmp_path: Path, partial_failure_summary: GenerationSummary) -> None:
        """Test that failed topic slugs and counts are written accurately."""
        output = tmp_path / "generation_summary.json"
        write_generation_summary(partial_failure_summary, output)

        data = json.loads(output.read_text())
        assert data["generation"]["failed_topics"] == 1
        assert data["generation"]["failed_topic_slugs"] == ["managing_replication_in_identity_management"]
        assert data["generation"]["generated"] == 261

    def test_no_temp_file_after_success(self, tmp_path: Path, all_success_summary: GenerationSummary) -> None:
        """Test that no temp file is left behind after a successful write."""
        output = tmp_path / "generation_summary.json"
        write_generation_summary(all_success_summary, output)

        tmp_files = list(tmp_path.glob(".tmp_generation_summary_*"))
        assert not tmp_files

    def test_creates_parent_directories(self, tmp_path: Path, all_success_summary: GenerationSummary) -> None:
        """Test that missing parent directories are created automatically."""
        output = tmp_path / "nested" / "dir" / "generation_summary.json"
        write_generation_summary(all_success_summary, output)
        assert output.exists()

    def test_output_is_valid_json(self, tmp_path: Path, all_success_summary: GenerationSummary) -> None:
        """Test that the written file is valid JSON with all expected top-level keys."""
        output = tmp_path / "generation_summary.json"
        write_generation_summary(all_success_summary, output)
        data = json.loads(output.read_text())
        assert isinstance(data, dict)
        assert set(data.keys()) >= {"generated_at", "report_versions", "settings", "source_documents", "generation", "output_path"}

    def test_write_error_raises_qa_write_error(self, tmp_path: Path, all_success_summary: GenerationSummary) -> None:
        """Test that writing to a directory path raises QAWriteError."""
        output = tmp_path / "generation_summary.json"
        output.mkdir()  # Make it a directory so writing fails
        with pytest.raises(QAWriteError):
            write_generation_summary(all_success_summary, output)
