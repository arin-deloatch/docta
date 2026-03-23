"""Extract and filter text snippets from diff reports for QA generation."""

from __future__ import annotations

from typing import Generator

import structlog
from doc_diff_tracker.models import HTMLChange, HTMLDiffReport, HTMLDiffResult

from qa_generation.models import (
    FilterConfig,
    QASourceDocument,
    SnippetExtractionStats,
    get_primary_text,
)

logger = structlog.get_logger(__name__)


def _passes_change_type_filter(change: HTMLChange, config: FilterConfig) -> bool:
    """Check if change passes change type filter."""
    return change.change_type in config.change_types


def _passes_text_length_filter(text: str, config: FilterConfig) -> bool:
    """Check if text passes length filter."""
    text_length = len(text)
    return config.min_text_length <= text_length <= config.max_text_length


def _passes_similarity_filter(result: HTMLDiffResult, config: FilterConfig) -> bool:
    """Check if result passes similarity filter."""
    return config.min_similarity <= result.text_similarity <= config.max_similarity


def _iter_filtered_changes(
    report: HTMLDiffReport,
    config: FilterConfig,
    stats: SnippetExtractionStats,
) -> Generator[tuple[HTMLDiffResult, HTMLChange, str], None, None]:
    """Iterate through filtered changes that pass all filter criteria.

    Filters are applied in order: similarity → type → text content → length.
    The stats object is mutated during iteration to track filtering metrics.

    Args:
        report: HTMLDiffReport to process
        config: FilterConfig with filtering rules
        stats: SnippetExtractionStats object that will be mutated to track
            filtering statistics. Must be consumed to completion for accurate stats.

    Yields:
        Tuple of (result, change, text) for changes that pass all filters
    """
    for result in report.results:
        # Filter by similarity first (result-level)
        if not _passes_similarity_filter(result, config):
            stats.filtered_by_similarity += len(result.changes)
            continue

        # Process each change in the result
        for change in result.changes:
            # Filter by change type
            if not _passes_change_type_filter(change, config):
                stats.filtered_by_type += 1
                continue

            # Get primary text
            text = get_primary_text(change)
            if not text:
                stats.filtered_no_text += 1
                continue

            # Filter by text length
            if not _passes_text_length_filter(text, config):
                stats.filtered_by_length += 1
                continue

            # This change passes all filters
            yield result, change, text


def extract_snippets(
    report: HTMLDiffReport,
    config: FilterConfig,
) -> list[QASourceDocument]:
    """Extract filtered text snippets from a diff report.

    Applies filtering rules from FilterConfig to extract only
    relevant changes suitable for QA generation.

    Args:
        report: HTMLDiffReport to extract snippets from
        config: FilterConfig with filtering rules

    Returns:
        List of QASourceDocument ready for RAGAS ingestion
    """
    logger.info(
        "extracting_snippets",
        old_version=report.old_version,
        new_version=report.new_version,
        total_results=len(report.results),
        filter_config={
            "change_types": list(config.change_types),
            "min_text_length": config.min_text_length,
            "max_text_length": config.max_text_length,
            "min_similarity": config.min_similarity,
            "max_similarity": config.max_similarity,
        },
    )

    stats = SnippetExtractionStats(
        total_results=len(report.results),
        total_changes=sum(len(r.changes) for r in report.results),
    )

    snippets: list[QASourceDocument] = []

    # Use shared filtering logic
    for result, change, text in _iter_filtered_changes(report, config, stats):
        # Convert to QASourceDocument
        try:
            snippet = QASourceDocument.from_html_change(
                change=change,
                topic_slug=result.new_topic_slug or result.old_topic_slug,
                report=report,
            )
            snippets.append(snippet)
            stats.extracted_snippets += 1
        except ValueError as e:
            logger.warning(
                "snippet_extraction_failed",
                topic_slug=result.new_topic_slug or result.old_topic_slug,
                location=change.location,
                error=str(e),
            )
            continue

    logger.info("snippet_extraction_complete", **stats.to_dict())

    return snippets


def extract_snippets_by_topic(
    report: HTMLDiffReport,
    config: FilterConfig,
) -> dict[str, list[QASourceDocument]]:
    """Extract snippets grouped by topic slug.

    This is useful when you want to generate QA pairs grouped
    by documentation topic/section.

    Args:
        report: HTMLDiffReport to extract snippets from
        config: FilterConfig with filtering rules

    Returns:
        Dictionary mapping topic_slug -> list of QASourceDocument
    """
    snippets = extract_snippets(report, config)

    # Group by topic_slug
    by_topic: dict[str, list[QASourceDocument]] = {}
    for snippet in snippets:
        if snippet.topic_slug not in by_topic:
            by_topic[snippet.topic_slug] = []
        by_topic[snippet.topic_slug].append(snippet)

    logger.info(
        "snippets_grouped_by_topic",
        total_snippets=len(snippets),
        unique_topics=len(by_topic),
        topics=list(by_topic.keys())[:10],  # Log first 10 topics
    )

    return by_topic


def preview_extraction(
    report: HTMLDiffReport,
    config: FilterConfig,
) -> dict[str, int]:
    """Preview snippet extraction without actually extracting.

    Useful for estimating how many snippets will be extracted
    without the overhead of creating QASourceDocument objects.

    Note: The 'would_pass_filters' count may be slightly higher than
    actual extraction count because it doesn't account for potential
    QASourceDocument.from_html_change() failures during extraction.

    Args:
        report: HTMLDiffReport to preview
        config: FilterConfig with filtering rules

    Returns:
        Dictionary with keys:
            - total_results: Number of diff results in report
            - total_changes: Total number of changes across all results
            - would_pass_filters: Number of changes that pass all filters
            - filtered_by_type: Changes filtered due to change type
            - filtered_by_length: Changes filtered due to text length
            - filtered_by_similarity: Changes filtered due to similarity
            - filtered_no_text: Changes filtered due to missing text
    """
    stats = SnippetExtractionStats(
        total_results=len(report.results),
        total_changes=sum(len(r.changes) for r in report.results),
    )

    # Count how many would pass filters using shared filtering logic
    would_pass_filters = sum(1 for _ in _iter_filtered_changes(report, config, stats))

    return {
        "total_results": stats.total_results,
        "total_changes": stats.total_changes,
        "would_pass_filters": would_pass_filters,
        "filtered_by_type": stats.filtered_by_type,
        "filtered_by_length": stats.filtered_by_length,
        "filtered_by_similarity": stats.filtered_by_similarity,
        "filtered_no_text": stats.filtered_no_text,
    }
