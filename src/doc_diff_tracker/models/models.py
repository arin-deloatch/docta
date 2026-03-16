"""Data models for document tracking and comparison."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


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
    """Record of a matched document pair between versions."""

    old_relative_path: str
    new_relative_path: str
    old_topic_slug: str
    new_topic_slug: str
    relationship: Literal[
        "unchanged",
        "modified",
        "renamed_candidate",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    similarity_score: float = Field(ge=0.0, le=100.0)
    raw_hash_equal: bool


class DeltaReport(BaseModel):
    """Complete report of differences between two documentation versions."""

    old_version: str
    new_version: str
    unchanged: list[MatchRecord]
    modified: list[MatchRecord]
    renamed_candidates: list[MatchRecord]
    removed: list[DocumentRecord]
    added: list[DocumentRecord]
