"""Data models for document tracking and comparison."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class RelationshipType(str, Enum):
    """Type of relationship between document versions."""

    UNCHANGED = "unchanged"
    MODIFIED = "modified"
    RENAMED_CANDIDATE = "renamed_candidate"


class DocumentRecord(BaseModel):
    """Record of a single HTML document in a corpus."""

    version: str
    root: str
    relative_path: str
    topic_slug: str
    html_filename: str
    raw_hash: str

    @property
    def path(self) -> Path:
        """Get absolute path to the document."""
        return Path(self.root) / self.relative_path


class MatchRecord(BaseModel):
    """
    Record of a matched document pair between versions.

    Note: topic_slug_similarity measures path/slug similarity, NOT content similarity.
    For content similarity, use the semantic diff report's text_similarity field.
    """

    old_relative_path: str
    new_relative_path: str
    old_topic_slug: str
    new_topic_slug: str
    relationship: RelationshipType
    confidence: float = Field(ge=0.0, le=1.0)
    topic_slug_similarity: float = Field(
        ge=0.0,
        le=100.0,
        description="Similarity of topic slugs (path-based), not document content",
    )
    raw_hash_equal: bool


class ManifestComparison(BaseModel):
    """Result of comparing two document manifests."""

    unchanged: list[MatchRecord]
    modified: list[MatchRecord]
    renamed_candidates: list[MatchRecord]
    removed: list[DocumentRecord]
    added: list[DocumentRecord]

    @property
    def total_changed(self) -> int:
        """Total number of changed documents."""
        return len(self.modified) + len(self.renamed_candidates)


class DeltaReport(BaseModel):
    """Complete report of differences between two documentation versions."""

    old_version: str
    new_version: str
    unchanged: list[MatchRecord]
    modified: list[MatchRecord]
    renamed_candidates: list[MatchRecord]
    removed: list[DocumentRecord]
    added: list[DocumentRecord]
