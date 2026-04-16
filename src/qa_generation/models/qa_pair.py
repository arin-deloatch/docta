"""Data models for QA pairs and generation configuration."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from docta.models import HTMLChange, HTMLDiffReport
from docta.utils.constants import MAX_METADATA_KEYS
from qa_generation.models.provider_config import EmbeddingConfig, LLMConfig

# Valid change types from HTMLChange model + document_added for new documents
ChangeType = Literal["text_change", "structure_change", "metadata_change", "document_added"]


class SourceDocumentInfo(BaseModel):
    """Traceability information from matched source document.

    This model stores the extracted metadata that links a QA pair
    back to its source document/change in the diff report.
    """

    topic_slug: str = Field(description="Topic slug from source document")
    location: str | None = Field(default=None, description="Location in source (e.g., section path)")
    change_type: str | None = Field(default=None, description="Type of change (text_change, structure_change, etc.)")
    versions: tuple[str, str] | None = Field(default=None, description="Source versions (old, new)")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata from source document (e.g., content fields)",
    )

    @model_validator(mode="after")
    def validate_metadata(self) -> "SourceDocumentInfo":
        """Validate metadata size and JSON-serializability."""
        _validate_metadata_size(self.metadata)
        return self


def _validate_metadata_size(metadata: dict[str, Any], max_keys: int = MAX_METADATA_KEYS) -> None:
    """Validate metadata dictionary size and JSON-serializability.

    Args:
        metadata: Metadata dictionary to validate
        max_keys: Maximum number of keys allowed

    Raises:
        ValueError: If metadata exceeds max_keys or contains non-serializable values
    """
    if len(metadata) > max_keys:
        raise ValueError(f"metadata cannot exceed {max_keys} keys, got {len(metadata)}")

    # Validate JSON-serializability
    try:
        json.dumps(metadata)
    except (TypeError, ValueError) as e:
        raise ValueError(f"metadata values must be JSON-serializable. Error: {e}") from e


class QASourceDocument(BaseModel):
    """Source document for QA generation.

    This model bridges the gap between semantic diff changes
    and RAGAS-compatible input format.
    """

    content: str
    topic_slug: str
    location: str | None = None
    change_type: str | None = None
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (max 100 keys, values must be JSON-serializable)",
    )

    @model_validator(mode="after")
    def validate_metadata(self) -> "QASourceDocument":
        """Validate metadata size and JSON-serializability."""
        _validate_metadata_size(self.metadata)
        return self

    @property
    def char_count(self) -> int:
        """Character count of the content."""
        return len(self.content)

    @property
    def word_count(self) -> int:
        """Approximate word count."""
        return len(self.content.split())

    @classmethod
    def from_html_change(
        cls,
        change: HTMLChange,
        topic_slug: str,
        report: HTMLDiffReport | None = None,
    ) -> "QASourceDocument":
        """Create a QASourceDocument from an HTMLChange.

        Args:
            change: HTMLChange object from semantic diff report
            topic_slug: Topic slug for the document
            report: Optional HTMLDiffReport to extract version info from

        Returns:
            QASourceDocument ready for RAGAS ingestion

        Raises:
            ValueError: If change has no text content
        """
        # Prefer new_text for current documentation state
        content = change.new_text or change.old_text

        if not content:
            raise ValueError(
                f"HTMLChange must have either new_text or old_text. "
                f"Got change_type={change.change_type!r}, location={change.location!r}, "
                f"new_text={bool(change.new_text)}, old_text={bool(change.old_text)}"
            )

        metadata = {}
        if report:
            metadata["versions"] = {
                "old": report.old_version,
                "new": report.new_version,
            }
        # Metadata dict accepts str values
        if change.description:
            metadata["change_description"] = change.description  # type: ignore[assignment]

        # Store old and new content for full traceability
        if change.old_text:
            metadata["old_content"] = change.old_text  # type: ignore[assignment]
        if change.new_text:
            metadata["new_content"] = change.new_text  # type: ignore[assignment]

        return cls(
            content=content,
            topic_slug=topic_slug,
            location=change.location,
            change_type=change.change_type,
            metadata=metadata,
        )


class QAPair(BaseModel):
    """A generated question-answer pair with full traceability.

    Includes metadata to trace back to the specific documentation
    change that generated this QA pair.
    """

    question: str
    ground_truth_answer: str
    source_topic_slug: str
    source_location: str | None = Field(default=None, description="Section path from the diff report")
    source_change_type: str | None = Field(default=None, description="Type of change (text_change, structure_change, etc.)")
    source_versions: tuple[str, str] | None = Field(default=None, description="(old_version, new_version) tuple")
    question_type: str | None = Field(
        default=None,
        description="Question type from RAGAS (e.g., specific, abstract, comparative)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata from generator (max 100 keys, JSON-serializable values)",
    )

    @model_validator(mode="after")
    def validate_metadata(self) -> "QAPair":
        """Validate metadata size and JSON-serializability."""
        _validate_metadata_size(self.metadata)
        return self

    @property
    def question_length(self) -> int:
        """Character length of the question."""
        return len(self.question)

    @property
    def answer_length(self) -> int:
        """Character length of the answer."""
        return len(self.ground_truth_answer)

    @property
    def has_traceability(self) -> bool:
        """Check if this QA pair has full traceability information."""
        return bool(self.source_topic_slug and self.source_location and self.source_versions and self.source_change_type)


class QueryDistribution(BaseModel):
    """Distribution of query types for RAGAS generation.

    Values must sum to 1.0 (within 0.01 tolerance).
    """

    specific: float = Field(default=0.5, ge=0.0, le=1.0, description="Simple, specific questions")
    abstract: float = Field(default=0.25, ge=0.0, le=1.0, description="Abstract reasoning questions")
    comparative: float = Field(default=0.25, ge=0.0, le=1.0, description="Comparative questions")

    @model_validator(mode="after")
    def validate_distribution_sum(self) -> "QueryDistribution":
        """Validate that distribution sums to approximately 1.0."""
        total = self.specific + self.abstract + self.comparative
        if abs(total - 1.0) >= 0.01:
            raise ValueError(f"Query distribution must sum to 1.0 (got {total:.3f}). " f"Adjust specific={self.specific}, abstract={self.abstract}, " f"comparative={self.comparative}")
        return self


class FilterConfig(BaseModel):
    """Configuration for filtering changes before QA generation."""

    min_text_length: int = Field(default=50, ge=0, description="Skip snippets shorter than this")
    max_text_length: int = Field(default=10000, ge=1, description="Skip snippets longer than this")
    change_types: set[ChangeType] = Field(
        default_factory=lambda: {"text_change"},  # type: ignore[arg-type]
        description="Which change types to use (text_change, structure_change, metadata_change)",
    )
    min_similarity: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Only generate from changes above this similarity",
    )
    max_similarity: float = Field(
        default=95.0,
        ge=0.0,
        le=100.0,
        description="Skip near-identical changes above this similarity",
    )

    @model_validator(mode="after")
    def validate_ranges(self) -> "FilterConfig":
        """Validate that min values are less than or equal to max values."""
        if self.min_text_length > self.max_text_length:
            raise ValueError(f"min_text_length ({self.min_text_length}) must be <= " f"max_text_length ({self.max_text_length})")
        if self.min_similarity > self.max_similarity:
            raise ValueError(f"min_similarity ({self.min_similarity}) must be <= " f"max_similarity ({self.max_similarity})")
        return self


class GeneratorConfig(BaseModel):
    """Complete configuration for QA generation.

    Validation is performed automatically via Pydantic validators:
    - QueryDistribution validates sum equals 1.0
    - FilterConfig validates min <= max for length and similarity ranges
    - Field validators enforce ge/le constraints
    """

    testset_size: int = Field(default=50, ge=1, description="Number of QA pairs to generate")
    query_distribution: QueryDistribution = Field(default_factory=QueryDistribution)
    filtering: FilterConfig = Field(default_factory=FilterConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    seed: int | None = Field(default=None, description="Random seed for reproducibility")
