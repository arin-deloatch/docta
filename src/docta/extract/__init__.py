"""Content extraction and semantic diffing."""

from docta.extract.block_differ import BlockChange, compare_documents
from docta.extract.content_extractor import extract_document_content

__all__ = ["extract_document_content", "compare_documents", "BlockChange"]
