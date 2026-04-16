"""Extract and filter text snippets from diff reports for QA generation."""

from __future__ import annotations

from collections import defaultdict
from typing import Generator

import structlog
from docta.utils.constants import MAX_TOPICS_TO_LOG

from qa_generation.models import (
    FilterConfig,
    HTMLChange,
    HTMLDiffReport,
    HTMLDiffResult,
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
) -> tuple[list[QASourceDocument], SnippetExtractionStats]:
    """Extract filtered text snippets from a diff report.

    Applies filtering rules from FilterConfig to extract only
    relevant changes suitable for QA generation.

    Args:
        report: HTMLDiffReport to extract snippets from
        config: FilterConfig with filtering rules

    Returns:
        Tuple of (list of QASourceDocument, extraction statistics)

    Raises:
        ValueError: If config.change_types is empty
    """
    if not config.change_types:
        raise ValueError("FilterConfig.change_types cannot be empty")

    if not report.results:
        logger.warning(
            "report_has_no_results",
            old_version=report.old_version,
            new_version=report.new_version,
        )

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
    # Note: full consumption of generator required for accurate stats
    for result, change, _text in _iter_filtered_changes(report, config, stats):
        # Get topic slug with explicit None handling
        topic_slug = result.new_topic_slug or result.old_topic_slug
        if topic_slug is None:
            logger.warning(
                "skipping_change_no_topic_slug",
                location=change.location,
                new_topic=result.new_topic_slug,
                old_topic=result.old_topic_slug,
            )
            stats.filtered_no_topic_slug += 1
            continue

        # Convert to QASourceDocument
        try:
            snippet = QASourceDocument.from_html_change(
                change=change,
                topic_slug=topic_slug,
                report=report,
            )
            snippets.append(snippet)
            stats.extracted_snippets += 1
        except ValueError as e:
            logger.warning(
                "snippet_extraction_failed",
                topic_slug=topic_slug,
                location=change.location,
                error=str(e),
            )
            continue

    logger.info("snippet_extraction_complete", **stats.to_dict())

    return snippets, stats


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
    snippets, _ = extract_snippets(report, config)

    # Group by topic_slug
    by_topic: dict[str, list[QASourceDocument]] = defaultdict(list)
    for snippet in snippets:
        by_topic[snippet.topic_slug].append(snippet)

    logger.info(
        "snippets_grouped_by_topic",
        total_snippets=len(snippets),
        unique_topics=len(by_topic),
        topics=list(by_topic.keys())[:MAX_TOPICS_TO_LOG],
    )

    return dict(by_topic)


def preview_extraction(
    report: HTMLDiffReport,
    config: FilterConfig,
) -> SnippetExtractionStats:
    """Preview snippet extraction without actually extracting.

    Useful for estimating how many snippets will be extracted
    without the overhead of creating QASourceDocument objects.

    Note: The extracted_snippets count may be slightly higher than
    actual extraction count because it doesn't account for potential
    QASourceDocument.from_html_change() failures during extraction.

    Args:
        report: HTMLDiffReport to preview
        config: FilterConfig with filtering rules

    Returns:
        SnippetExtractionStats with extracted_snippets representing the
        number of changes that would pass all filters

    Raises:
        ValueError: If config.change_types is empty
    """
    if not config.change_types:
        raise ValueError("FilterConfig.change_types cannot be empty")

    stats = SnippetExtractionStats(
        total_results=len(report.results),
        total_changes=sum(len(r.changes) for r in report.results),
    )

    # Count how many would pass filters using shared filtering logic
    # Note: full consumption required for accurate stats
    stats.extracted_snippets = sum(1 for _ in _iter_filtered_changes(report, config, stats))

    return stats
