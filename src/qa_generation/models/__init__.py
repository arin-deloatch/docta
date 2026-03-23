"""Data models for QA generation."""

from qa_generation.models.extraction_stats import SnippetExtractionStats
from qa_generation.models.qa_pair import (
    EmbeddingConfig,
    FilterConfig,
    GeneratorConfig,
    LLMConfig,
    QAPair,
    QASourceDocument,
    QueryDistribution,
)
from qa_generation.models.report_ingestion import (
    HTMLChange,
    HTMLDiffReport,
    HTMLDiffResult,
    count_text_changes,
    filter_by_change_type,
    filter_by_similarity,
    get_primary_text,
    get_text_changes,
)

__all__ = [
    # Report ingestion models
    "HTMLChange",
    "HTMLDiffResult",
    "HTMLDiffReport",
    # Report ingestion functions
    "get_text_changes",
    "filter_by_similarity",
    "filter_by_change_type",
    "get_primary_text",
    "count_text_changes",
    # QA pairs and config
    "QAPair",
    "QASourceDocument",
    "GeneratorConfig",
    "QueryDistribution",
    "FilterConfig",
    "LLMConfig",
    "EmbeddingConfig",
    # Extraction stats
    "SnippetExtractionStats",
]
