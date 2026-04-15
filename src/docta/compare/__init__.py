"""Document comparison and lineage tracking."""

from docta.compare.lineage import compare_manifests
from docta.compare.semantic_diff import (
    compare_html_documents_semantic,
    process_match_record_semantic,
)

__all__ = [
    "compare_manifests",
    "compare_html_documents_semantic",
    "process_match_record_semantic",
]
