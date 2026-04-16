"""Report ingestion utilities for QA generation.

Re-exports models from docta and provides filtering functions
for preparing semantic diff reports for QA generation.
"""

# pylint: disable=duplicate-code

from __future__ import annotations

from docta.models import HTMLChange, HTMLDiffReport, HTMLDiffResult

# Re-export for convenience
__all__ = [
    "HTMLChange",
    "HTMLDiffResult",
    "HTMLDiffReport",
    "get_text_changes",
    "filter_by_similarity",
    "filter_by_change_type",
    "get_primary_text",
    "count_text_changes",
]


def get_text_changes(result: HTMLDiffResult) -> list[HTMLChange]:
    """Extract only text changes with content from a diff result.

    Args:
        result: A single HTMLDiffResult

    Returns:
        List of text changes that have old_text or new_text
    """
    return [change for change in result.changes if change.change_type == "text_change" and (change.old_text or change.new_text)]


def filter_by_similarity(
    report: HTMLDiffReport,
    min_similarity: float = 0.0,
    max_similarity: float = 100.0,
) -> list[HTMLDiffResult]:
    """Filter diff results by text similarity range.

    Useful for focusing on changes that are neither too similar
    (trivial changes) nor too different (complete rewrites).

    Args:
        report: The semantic diff report
        min_similarity: Minimum similarity score (inclusive, 0.0-100.0)
        max_similarity: Maximum similarity score (inclusive, 0.0-100.0)

    Returns:
        Filtered list of diff results

    Raises:
        ValueError: If similarity values are out of range or min > max
    """
    if not 0.0 <= min_similarity <= 100.0:
        raise ValueError(f"min_similarity must be between 0.0 and 100.0, got {min_similarity}")
    if not 0.0 <= max_similarity <= 100.0:
        raise ValueError(f"max_similarity must be between 0.0 and 100.0, got {max_similarity}")
    if min_similarity > max_similarity:
        raise ValueError(f"min_similarity ({min_similarity}) must be <= " f"max_similarity ({max_similarity})")

    return [result for result in report.results if min_similarity <= result.text_similarity <= max_similarity]


def filter_by_change_type(result: HTMLDiffResult, change_types: set[str]) -> list[HTMLChange]:
    """Filter changes by type.

    Args:
        result: A single HTMLDiffResult
        change_types: Set of change types to include

    Returns:
        Filtered list of changes
    """
    return [change for change in result.changes if change.change_type in change_types]


def get_primary_text(change: HTMLChange) -> str | None:
    """Get the primary text for QA generation.

    Prefers new_text (for additions/modifications) but falls back to
    old_text (for deletions). Returns None if both are absent.

    For most QA use cases, new_text represents the current state of
    documentation and is preferred for generating questions about
    current functionality.

    Args:
        change: The change to extract text from

    Returns:
        The new_text if available, otherwise old_text, or None
    """
    return change.new_text or change.old_text


def count_text_changes(report: HTMLDiffReport) -> int:
    """Count total text changes with content across all results.

    Args:
        report: The semantic diff report

    Returns:
        Total count of text changes
    """
    total = 0
    for result in report.results:
        total += len(get_text_changes(result))
    return total
