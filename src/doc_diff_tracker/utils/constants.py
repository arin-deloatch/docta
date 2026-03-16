"""Configuration constants for doc-diff-tracker."""

from __future__ import annotations

# File processing limits
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB per file
MAX_FILES_TO_PROCESS = 10_000  # Prevent processing excessive files

# Allowed file extensions
ALLOWED_EXTENSIONS = {".html", ".htm"}
