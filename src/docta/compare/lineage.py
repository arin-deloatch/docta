"""Document manifest comparison and lineage tracking."""

from __future__ import annotations

import structlog
from rapidfuzz import fuzz

from docta.models.models import (
    DocumentRecord,
    MatchRecord,
    ManifestComparison,
    RelationshipType,
)
from docta.utils.constants import DEFAULT_EXCLUDE_FROM_RENAME

logger = structlog.get_logger(__name__)


def _similarity(old_doc: DocumentRecord, new_doc: DocumentRecord) -> float:
    """Calculate similarity between two documents using topic slug."""
    return fuzz.ratio(old_doc.topic_slug, new_doc.topic_slug)


def _should_exclude_from_rename(topic_slug: str, exclude_patterns: set[str]) -> bool:
    """Check if a topic slug should be excluded from rename detection."""
    return any(pattern in topic_slug for pattern in exclude_patterns)


def _create_match_record(
    old_doc: DocumentRecord,
    new_doc: DocumentRecord,
    relationship: RelationshipType,
    confidence: float,
    topic_slug_similarity: float,
) -> MatchRecord:
    """
    Create a MatchRecord from two documents.

    Args:
        old_doc: Document from old version
        new_doc: Document from new version
        relationship: Type of match (unchanged/modified/renamed_candidate)
        confidence: Confidence level (0.0-1.0)
        topic_slug_similarity: Topic slug similarity score (0-100)
            - 100.0 for exact slug matches (unchanged/modified)
            - Variable for fuzzy matches (renamed_candidate)
    """
    raw_equal = old_doc.raw_hash == new_doc.raw_hash
    return MatchRecord(
        old_relative_path=old_doc.relative_path,
        new_relative_path=new_doc.relative_path,
        old_topic_slug=old_doc.topic_slug,
        new_topic_slug=new_doc.topic_slug,
        relationship=relationship,
        confidence=confidence,
        topic_slug_similarity=topic_slug_similarity,
        raw_hash_equal=raw_equal,
    )


def _find_exact_match(
    old_doc: DocumentRecord,
    new_docs_by_slug: dict[str, DocumentRecord],
    matched_paths: set[str],
) -> MatchRecord | None:
    """Find exact topic slug match for an old document."""
    exact = new_docs_by_slug.get(old_doc.topic_slug)
    if not exact:
        return None

    matched_paths.add(exact.relative_path)
    raw_equal = old_doc.raw_hash == exact.raw_hash
    relationship = RelationshipType.UNCHANGED if raw_equal else RelationshipType.MODIFIED

    return _create_match_record(old_doc, exact, relationship, confidence=1.0, topic_slug_similarity=100.0)


def _find_best_rename_candidate(
    old_doc: DocumentRecord,
    new_docs: list[DocumentRecord],
    matched_paths: set[str],
    exclude_patterns: set[str],
    threshold: float,
) -> tuple[DocumentRecord, float] | None:
    """Find best rename candidate for an old document."""
    best_doc = None
    best_score = -1.0

    for new_doc in new_docs:
        if new_doc.relative_path in matched_paths:
            continue
        if _should_exclude_from_rename(new_doc.topic_slug, exclude_patterns):
            continue

        score = _similarity(old_doc, new_doc)
        if score > best_score:
            best_doc = new_doc
            best_score = score

    if best_doc is not None and best_score >= threshold:
        return best_doc, best_score
    return None


def compare_manifests(  # pylint: disable=too-many-locals
    old_docs: list[DocumentRecord],
    new_docs: list[DocumentRecord],
    rename_threshold: float = 85.0,
    exclude_from_rename: set[str] | None = None,
) -> ManifestComparison:
    """
    Compare two document manifests to identify changes.

    Args:
        old_docs: Documents from older version
        new_docs: Documents from newer version
        rename_threshold: Similarity threshold (0-100) for detecting renames
        exclude_from_rename: Set of patterns to exclude from rename detection

    Returns:
        ManifestComparison with categorized document changes
    """
    logger.info(
        "comparing_manifests",
        old_docs=len(old_docs),
        new_docs=len(new_docs),
        rename_threshold=rename_threshold,
    )

    if exclude_from_rename is None:
        exclude_from_rename = set(DEFAULT_EXCLUDE_FROM_RENAME)

    new_docs_by_slug = {doc.topic_slug: doc for doc in new_docs}
    matched_paths: set[str] = set()

    unchanged: list[MatchRecord] = []
    modified: list[MatchRecord] = []
    renamed_candidates: list[MatchRecord] = []
    removed: list[DocumentRecord] = []

    for old_doc in old_docs:
        # Try exact match first
        exact_match = _find_exact_match(old_doc, new_docs_by_slug, matched_paths)
        if exact_match:
            if exact_match.raw_hash_equal:
                unchanged.append(exact_match)
            else:
                modified.append(exact_match)
            continue

        # Skip rename detection for excluded patterns
        if _should_exclude_from_rename(old_doc.topic_slug, exclude_from_rename):
            removed.append(old_doc)
            continue

        # Try rename detection
        rename_result = _find_best_rename_candidate(old_doc, new_docs, matched_paths, exclude_from_rename, rename_threshold)
        if rename_result:
            best_doc, best_score = rename_result
            matched_paths.add(best_doc.relative_path)
            match = _create_match_record(
                old_doc,
                best_doc,
                relationship=RelationshipType.RENAMED_CANDIDATE,
                confidence=min(best_score / 100.0, 0.99),
                topic_slug_similarity=best_score,
            )
            renamed_candidates.append(match)
        else:
            removed.append(old_doc)

    added = [doc for doc in new_docs if doc.relative_path not in matched_paths]

    logger.info(
        "manifest_comparison_complete",
        unchanged=len(unchanged),
        modified=len(modified),
        renamed_candidates=len(renamed_candidates),
        removed=len(removed),
        added=len(added),
    )

    return ManifestComparison(
        unchanged=unchanged,
        modified=modified,
        renamed_candidates=renamed_candidates,
        removed=removed,
        added=added,
    )
