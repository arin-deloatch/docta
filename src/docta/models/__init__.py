"""Data models for document tracking and comparison."""

from docta.models.content import (
    CodeBlock,
    DocumentMetadata,
    ExtractedDocument,
    Heading,
    ImageBlock,
    LinkBlock,
    ListBlock,
    Section,
    TableBlock,
    TextBlock,
)
from docta.models.html_diff import (
    FailedComparison,
    HTMLChange,
    HTMLDiffReport,
    HTMLDiffResult,
    ProcessingResult,
)
from docta.models.models import (
    DeltaReport,
    DocumentRecord,
    ManifestComparison,
    MatchRecord,
    RelationshipType,
)

__all__ = [
    # Core models
    "DocumentRecord",
    "MatchRecord",
    "ManifestComparison",
    "DeltaReport",
    "RelationshipType",
    # Content models
    "TextBlock",
    "CodeBlock",
    "ListBlock",
    "TableBlock",
    "Heading",
    "ImageBlock",
    "LinkBlock",
    "Section",
    "DocumentMetadata",
    "ExtractedDocument",
    # HTML diff models
    "HTMLChange",
    "HTMLDiffResult",
    "FailedComparison",
    "ProcessingResult",
    "HTMLDiffReport",
]
