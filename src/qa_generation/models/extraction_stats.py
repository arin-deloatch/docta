"""Statistics models for snippet extraction."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SnippetExtractionStats(BaseModel):
    """Statistics about snippet extraction process."""

    total_results: int = Field(default=0, ge=0)
    total_changes: int = Field(default=0, ge=0)
    filtered_by_type: int = Field(default=0, ge=0)
    filtered_by_length: int = Field(default=0, ge=0)
    filtered_by_similarity: int = Field(default=0, ge=0)
    filtered_no_text: int = Field(default=0, ge=0)
    extracted_snippets: int = Field(default=0, ge=0)

    def to_dict(self) -> dict[str, int]:
        """Convert stats to dictionary for logging."""
        return {
            "total_results": self.total_results,
            "total_changes": self.total_changes,
            "extracted_snippets": self.extracted_snippets,
            "filtered_by_type": self.filtered_by_type,
            "filtered_by_length": self.filtered_by_length,
            "filtered_by_similarity": self.filtered_by_similarity,
            "filtered_no_text": self.filtered_no_text,
        }

    @property
    def total_filtered(self) -> int:
        """Total number of filtered items."""
        return (
            self.filtered_by_type
            + self.filtered_by_length
            + self.filtered_by_similarity
            + self.filtered_no_text
        )

    @property
    def extraction_rate(self) -> float:
        """Percentage of changes successfully extracted."""
        if self.total_changes == 0:
            return 0.0
        return (self.extracted_snippets / self.total_changes) * 100
