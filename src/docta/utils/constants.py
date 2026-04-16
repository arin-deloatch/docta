"""Configuration constants for docta."""

from __future__ import annotations

from typing import Literal

# File processing limits
BYTES_PER_MB = 1024 * 1024  # Conversion factor: MB to bytes
DOWNLOAD_CHUNK_SIZE_BYTES = 8192  # HTTP download chunk size
MAX_FILE_SIZE_BYTES = 10 * BYTES_PER_MB  # 10MB per file
MAX_REPORT_SIZE_BYTES = 100 * BYTES_PER_MB  # 100MB for aggregate reports
MAX_FILES_TO_PROCESS = 10_000  # Prevent processing excessive files

# Allowed file extensions
ALLOWED_EXTENSIONS = {".html", ".htm"}

# Block-level change types
BlockChangeType = Literal[
    "section_added",
    "section_removed",
    "section_modified",
    "heading_changed",
    "text_added",
    "text_removed",
    "text_modified",
    "code_added",
    "code_removed",
    "code_modified",
    "table_added",
    "table_removed",
    "table_modified",
    "list_added",
    "list_removed",
    "list_modified",
    "image_added",
    "image_removed",
    "image_modified",
    "link_added",
    "link_removed",
    "metadata_changed",
]

# HTML change type category
HTMLChangeCategory = Literal["text_change", "structure_change", "metadata_change"]

# HTML change type mappings
TYPE_MAPPING: dict[BlockChangeType, HTMLChangeCategory] = {
    "section_added": "structure_change",
    "section_removed": "structure_change",
    "section_modified": "structure_change",
    "heading_changed": "structure_change",
    "text_added": "text_change",
    "text_removed": "text_change",
    "text_modified": "text_change",
    "code_added": "structure_change",
    "code_removed": "structure_change",
    "code_modified": "text_change",
    "table_added": "structure_change",
    "table_removed": "structure_change",
    "table_modified": "text_change",
    "list_added": "structure_change",
    "list_removed": "structure_change",
    "list_modified": "text_change",
    "image_added": "structure_change",
    "image_removed": "structure_change",
    "image_modified": "structure_change",
    "link_added": "structure_change",
    "link_removed": "structure_change",
    "metadata_changed": "metadata_change",
}

# Structural change types (for detecting structural changes)
STRUCTURAL_CHANGE_TYPES: set[str] = {
    "section_added",
    "section_removed",
    "heading_changed",
    "code_added",
    "code_removed",
    "table_added",
    "table_removed",
    "list_added",
    "list_removed",
    "image_added",
    "image_removed",
    "link_added",
    "link_removed",
}

# Content extraction constants
MAX_CONTENT_PREVIEW_LENGTH = 500  # Max characters for content preview in diffs
MAX_HTML_SNIPPET_LENGTH = 1000  # Max characters for stored HTML snippets
MIN_TEXT_LENGTH = 3  # Minimum text length to consider for extraction
MAX_SECTION_DEPTH = 10  # Maximum nesting depth for sections
MAX_PREVIEW_BLOCKS = 3  # Maximum number of blocks to include in HTML snippets

# Fuzzy matching thresholds
SECTION_MATCH_THRESHOLD = 85.0  # Minimum similarity for section matching (0-100)

# Security constants
FORBIDDEN_SYSTEM_DIRS = frozenset({"/etc", "/sys", "/proc", "/dev", "/boot", "/root"})  # System directories forbidden for writing

# Document comparison constants
DEFAULT_EXCLUDE_FROM_RENAME = frozenset({"release_notes"})  # Topic slugs to exclude from rename detection by default

# HTML element sets for content extraction
CONTAINER_ELEMENTS = frozenset({"div", "section", "article", "main", "body", "html"})
BLOCK_LEVEL_ELEMENTS = frozenset(
    {
        "p",
        "div",
        "section",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "ul",
        "ol",
        "table",
        "pre",
    }
)
HEADING_ELEMENTS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
LIST_ELEMENTS = frozenset({"ul", "ol"})
CODE_ELEMENTS = frozenset({"pre", "code"})
STRUCTURED_CONTENT_ELEMENTS = frozenset({"ul", "ol", "table", "pre", "code", "img", "a"})
BLOCK_EXTRACTION_ELEMENTS = frozenset({"p", "pre", "ul", "ol", "table", "code"})

# QA Generation constants
MIN_CONTENT_LENGTH_FOR_MATCHING = 50  # Minimum content length for similarity matching
QA_CONTENT_PREVIEW_LENGTH = 100  # Preview length for content matching
MAX_METADATA_KEYS = 100  # Maximum keys in QA pair metadata
MAX_TOPICS_TO_LOG = 10  # Maximum topics to log in snippet extraction

# Document traceability markers for QA generation
DOC_ID_MARKER_TEMPLATE = "<!--DOC_ID:{}-->\n{}"  # Template for embedding doc IDs
DOC_ID_PATTERN_STR = r"<!--DOC_ID:(\d+)-->"  # Regex pattern for extracting doc IDs
