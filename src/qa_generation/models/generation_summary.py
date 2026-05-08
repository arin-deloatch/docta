"""Generation summary artifact model for QA pipeline runs.

The generation_summary.json schema mirrors this model:

{
    "generated_at": "2026-05-08T12:00:00+00:00",
    "report_versions": {"old": "9", "new": "10"},
    "settings": {
        "testset_size": 300,
        "llm": {"provider": "google", "model": "gemini-2.5-flash", "temperature": 0.3},
        "embedding": {"provider": "google", "model": "models/text-embedding-004"},
        "query_distribution": {"specific": 0.5, "abstract": 0.25, "comparative": 0.25},
        "filtering": {...},
        "seed": null
    },
    "source_documents": {"total": 42, "topics": 8},
    "generation": {
        "requested": 300,
        "generated": 261,
        "failed_topics": 1,
        "failed_topic_slugs": ["managing_replication_in_identity_management"]
    },
    "output_path": "output/qa_pairs.json"
}
"""

from __future__ import annotations

from pydantic import BaseModel, Field, computed_field

from qa_generation.models.qa_pair import GeneratorConfig


class ReportVersions(BaseModel):
    """Old and new documentation versions from the source report."""

    old: str = Field(description="Old documentation version")
    new: str = Field(description="New documentation version")


class SourceDocumentsSummary(BaseModel):
    """Count of source documents passed to generation after all filtering."""

    total: int = Field(ge=0, description="Total source documents processed")
    topics: int = Field(ge=0, description="Unique topic slugs across source documents")


class GenerationStats(BaseModel):
    """Generation counts and failure tracking."""

    requested: int = Field(ge=0, description="Number of QA pairs requested")
    generated: int = Field(ge=0, description="Number of QA pairs successfully generated")
    failed_topic_slugs: list[str] = Field(default_factory=list, description="Topic slugs that failed generation")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def failed_topics(self) -> int:
        """Derived from failed_topic_slugs to ensure count and list never diverge."""
        return len(self.failed_topic_slugs)


class GenerationSummary(BaseModel):
    """Summary artifact written alongside QA pairs output.

    Written atomically as generation_summary.json in the same directory
    as the QA pairs output file after every successful pipeline run.
    Provides a structured record of run quality without requiring log access.
    """

    generated_at: str = Field(description="ISO 8601 timestamp of when generation completed")
    report_versions: ReportVersions
    settings: GeneratorConfig
    source_documents: SourceDocumentsSummary
    generation: GenerationStats
    output_path: str = Field(description="Path to the QA pairs output file")
