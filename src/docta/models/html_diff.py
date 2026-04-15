"""Data models for HTML diff results."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HTMLChange(BaseModel):
    """Represents a notable change between two HTML documents."""

    change_type: Literal["text_change", "structure_change", "metadata_change"]
    description: str
    old_html_snippet: str | None = None
    new_html_snippet: str | None = None
    old_text: str | None = None
    new_text: str | None = None
    location: str | None = None


class HTMLDiffResult(BaseModel):
    """Result of comparing two HTML documents."""

    old_path: str
    new_path: str
    old_topic_slug: str
    new_topic_slug: str
    relationship: str
    changes: list[HTMLChange]
    text_similarity: float = Field(ge=0.0, le=100.0)
    has_structural_changes: bool


class FailedComparison(BaseModel):
    """Represents a failed document comparison."""

    old_path: str
    new_path: str
    error_type: str
    error_message: str


class ProcessingResult(BaseModel):
    """Result of processing a single document pair."""

    success: bool
    result: HTMLDiffResult | None = None
    failure: FailedComparison | None = None


class HTMLDiffReport(BaseModel):
    """Collection of HTML diff results."""

    old_version: str
    new_version: str
    old_root: str
    new_root: str
    results: list[HTMLDiffResult]
    failed_comparisons: list[FailedComparison] = Field(default_factory=list)
    total_compared: int
    total_with_changes: int
    total_failed: int = 0
