"""Inventory and manifest building utilities."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Generator

import structlog

from docta.models.models import DocumentRecord
from docta.utils.constants import ALLOWED_EXTENSIONS, MAX_FILES_TO_PROCESS
from docta.utils.security import SecurityError, validate_file_for_reading

logger = structlog.get_logger(__name__)


def sha256_bytes(data: bytes) -> str:
    """Calculate SHA256 hash of bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    """Calculate SHA256 hash of text string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def iter_html_docs(root: Path, allow_symlinks: bool = False) -> Generator[Path, None, None]:
    """Yield HTML files found recursively under root."""
    file_count = 0

    for html_path in root.rglob("*.html"):
        file_count += 1
        if file_count > MAX_FILES_TO_PROCESS:
            raise SecurityError(f"Too many files to process (limit: {MAX_FILES_TO_PROCESS:,}). " "Consider using a more specific directory.")

        if not allow_symlinks and html_path.is_symlink():
            logger.debug("skipping_symlinked_file", path=str(html_path))
            continue

        yield html_path


def _process_html_file(html_path: Path, root_path: Path, version: str) -> DocumentRecord | None:
    """
    Process a single HTML file into a DocumentRecord.

    Returns:
        DocumentRecord if successful, None if file should be skipped
    """
    try:
        validate_file_for_reading(html_path, allowed_extensions=ALLOWED_EXTENSIONS)

        relative_path = str(html_path.relative_to(root_path))
        parts = html_path.relative_to(root_path).parts
        topic_slug = parts[0] if parts else html_path.stem

        raw_bytes = html_path.read_bytes()

        # Validate UTF-8 encoding
        try:
            raw_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as e:
            logger.warning("skipping_invalid_utf8", path=str(html_path), error=str(e))
            return None

        return DocumentRecord(
            version=version,
            root=str(root_path),
            relative_path=relative_path,
            topic_slug=topic_slug,
            html_filename=html_path.name,
            raw_hash=sha256_bytes(raw_bytes),
        )
    except SecurityError as e:
        logger.warning("skipping_security_check", path=str(html_path), error=str(e))
        return None
    except (OSError, ValueError, RuntimeError) as e:
        logger.error("error_processing_file", path=str(html_path), error=str(e))
        return None


def build_manifest(
    root: str,
    version: str,
    allow_symlinks: bool = False,
) -> list[DocumentRecord]:
    """
    Build a manifest of all HTML documents in the corpus.

    Args:
        root: Root directory path
        version: Version label for this corpus
        allow_symlinks: If True, process symlinked files

    Returns:
        List of DocumentRecord objects sorted by relative path
    """
    root_path = Path(root)
    records: list[DocumentRecord] = []
    skipped_files = 0

    for html_path in iter_html_docs(root_path, allow_symlinks=allow_symlinks):
        record = _process_html_file(html_path, root_path, version)
        if record:
            records.append(record)
        else:
            skipped_files += 1

    if skipped_files > 0:
        logger.info("skipped_files", count=skipped_files, reason="validation_failures")

    return sorted(records, key=lambda r: r.relative_path)
