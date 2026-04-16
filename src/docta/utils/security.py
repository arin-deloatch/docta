"""Security validation utilities for safe file operations."""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Optional

from docta.utils.constants import (
    FORBIDDEN_SYSTEM_DIRS,
    MAX_FILE_SIZE_BYTES,
)


class SecurityError(Exception):
    """Raised when security validation fails."""


def validate_input_directory(
    path_str: str,
    must_exist: bool = True,
    allow_symlinks: bool = False,
    allowed_base: Optional[Path] = None,
) -> Path:
    """
    Validate and resolve an input directory path.

    Args:
        path_str: User-provided path string
        must_exist: If True, path must exist
        allow_symlinks: If False, reject symlinked directories
        allowed_base: If provided, path must be within this directory

    Returns:
        Resolved absolute Path object

    Raises:
        SecurityError: If validation fails
    """
    try:
        # Resolve to absolute path (prevents relative path tricks)
        path = Path(path_str).resolve(strict=must_exist)
    except (OSError, RuntimeError) as e:
        raise SecurityError(f"Invalid path '{path_str}': {e}") from e

    # Check existence
    if must_exist and not path.exists():
        raise SecurityError(f"Path does not exist: {path}")

    # Check it's a directory
    if must_exist and not path.is_dir():
        raise SecurityError(f"Path is not a directory: {path}")

    # Check for symlink (optional)
    if not allow_symlinks and path.is_symlink():
        raise SecurityError(f"Symlinked directories not allowed: {path}")

    # Check path is within allowed base directory (prevents ../../../etc)
    if allowed_base is not None:
        try:
            path.relative_to(allowed_base.resolve())
        except ValueError as exc:
            raise SecurityError(f"Path '{path}' is outside allowed directory '{allowed_base}'") from exc

    return path


def _check_forbidden_system_dirs(path: Path) -> None:
    """Check if path is in a forbidden system directory."""
    for forbidden in FORBIDDEN_SYSTEM_DIRS:
        try:
            path.relative_to(forbidden)
            raise SecurityError(f"Writing to system directory forbidden: {forbidden}")
        except ValueError:
            continue


def validate_output_path(
    path_str: str,
    allowed_extensions: Optional[set[str]] = None,
    allow_overwrite: bool = False,
) -> Path:
    """
    Validate an output file path.

    Args:
        path_str: User-provided output path
        allowed_extensions: Set of allowed file extensions
        allow_overwrite: If False, reject if file already exists

    Returns:
        Resolved absolute Path object
    """
    try:
        path = Path(path_str).resolve()
    except (OSError, RuntimeError) as e:
        raise SecurityError(f"Invalid output path '{path_str}': {e}") from e

    if allowed_extensions and path.suffix.lower() not in allowed_extensions:
        raise SecurityError(f"Invalid extension '{path.suffix}'. " f"Allowed: {', '.join(sorted(allowed_extensions))}")

    if not path.parent.exists():
        raise SecurityError(f"Parent directory does not exist: {path.parent}")

    if not os.access(path.parent, os.W_OK):
        raise SecurityError(f"Parent directory not writable: {path.parent}")

    if not allow_overwrite and path.exists():
        raise SecurityError(f"File already exists (use --allow-overwrite): {path}")

    _check_forbidden_system_dirs(path)
    return path


def validate_file_for_reading(
    file_path: Path,
    max_size: int = MAX_FILE_SIZE_BYTES,
    allowed_extensions: Optional[set[str]] = None,
) -> None:
    """Validate a file is safe to read."""
    if not file_path.is_file():
        raise SecurityError(f"Not a regular file: {file_path}")

    if file_path.is_symlink():
        raise SecurityError(f"Symlinked files not allowed: {file_path}")

    if allowed_extensions and file_path.suffix.lower() not in allowed_extensions:
        raise SecurityError(f"Extension '{file_path.suffix}' not allowed: {file_path}")

    try:
        file_size = file_path.stat().st_size
    except OSError as e:
        raise SecurityError(f"Cannot stat file {file_path}: {e}") from e

    if file_size > max_size:
        raise SecurityError(f"File too large: {file_path} ({file_size:,} bytes, max {max_size:,})")


def validate_float_parameter(
    value: float,
    name: str,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
) -> float:
    """Validate a float parameter is within acceptable range."""
    if math.isnan(value) or math.isinf(value):
        raise SecurityError(f"Parameter '{name}' must be finite")

    if min_val is not None and value < min_val:
        raise SecurityError(f"Parameter '{name}' must be >= {min_val}, got {value}")

    if max_val is not None and value > max_val:
        raise SecurityError(f"Parameter '{name}' must be <= {max_val}, got {value}")

    return value


def validate_version_string(version: str, max_length: int = 50) -> str:
    """Validate a version string is safe."""
    if not version:
        raise SecurityError("Version string cannot be empty")

    if len(version) > max_length:
        raise SecurityError(f"Version string too long (max {max_length} chars)")

    forbidden_chars = {"/", "\\", "\0", "..", "\n", "\r"}
    for char in forbidden_chars:
        if char in version:
            raise SecurityError(f"Version contains forbidden character: {char}")

    return version
