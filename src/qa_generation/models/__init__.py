"""Data models for QA generation."""

from qa_generation.models.extraction_stats import (
    AddedDocumentStats,
    SnippetExtractionStats,
)
from qa_generation.models.provider_config import EmbeddingConfig, LLMConfig
from qa_generation.models.qa_pair import (
    FilterConfig,
    GeneratorConfig,
    QAPair,
    QASourceDocument,
    QueryDistribution,
    SourceDocumentInfo,
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

__all__ = [  # pylint: disable=duplicate-code
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
    "SourceDocumentInfo",
    "GeneratorConfig",
    "QueryDistribution",
    "FilterConfig",
    # Provider configs
    "LLMConfig",
    "EmbeddingConfig",
    # Extraction stats
    "SnippetExtractionStats",
    "AddedDocumentStats",
]
