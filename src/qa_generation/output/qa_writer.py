"""Write QA pairs to output files."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import structlog
import yaml

from qa_generation.models import QAPair

logger = structlog.get_logger(__name__)


class QAWriteError(Exception):
    """Raised when writing QA pairs fails."""


def write_qa_pairs_json(
    qa_pairs: list[QAPair],
    output_path: str | Path,
    indent: int = 2,
    allow_overwrite: bool = False,
) -> None:
    """Write QA pairs to JSON file with atomic write.

    Uses atomic write (temp file + rename) to prevent corruption
    if write is interrupted.

    Args:
        qa_pairs: List of QAPair objects to write
        output_path: Path to output JSON file
        indent: JSON indentation level
        allow_overwrite: If False, raise error if file exists

    Raises:
        QAWriteError: If write fails or file exists (when allow_overwrite=False)
    """
    output_path = Path(output_path)

    logger.info(
        "writing_qa_pairs_json",
        output_path=str(output_path),
        count=len(qa_pairs),
        allow_overwrite=allow_overwrite,
    )

    # Check if file exists
    if not allow_overwrite and output_path.exists():
        raise QAWriteError(f"Output file already exists (use allow_overwrite=True): {output_path}")

    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Serialize to dict
    qa_dicts = [qa.model_dump(mode="python") for qa in qa_pairs]

    # Write to temporary file first (atomic write)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=".tmp_qa_pairs_",
            suffix=".json",
            delete=False,
        ) as tmp_file:
            json.dump(qa_dicts, tmp_file, indent=indent, ensure_ascii=False)
            tmp_path = Path(tmp_file.name)

        # Atomic rename
        tmp_path.replace(output_path)

        logger.info(
            "qa_pairs_written_successfully",
            output_path=str(output_path),
            count=len(qa_pairs),
            size_bytes=output_path.stat().st_size,
        )

    except (OSError, IOError) as e:
        # Clean up temp file if it exists
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()
        logger.error("qa_write_failed", output_path=str(output_path), error=str(e))
        raise QAWriteError(f"Failed to write QA pairs: {e}") from e


def write_qa_pairs_yaml(
    qa_pairs: list[QAPair],
    output_path: str | Path,
    allow_overwrite: bool = False,
) -> None:
    """Write QA pairs to YAML file with atomic write.

    Uses atomic write (temp file + rename) to prevent corruption
    if write is interrupted.

    Args:
        qa_pairs: List of QAPair objects to write
        output_path: Path to output YAML file
        allow_overwrite: If False, raise error if file exists

    Raises:
        QAWriteError: If write fails or file exists (when allow_overwrite=False)
    """
    output_path = Path(output_path)

    logger.info(
        "writing_qa_pairs_yaml",
        output_path=str(output_path),
        count=len(qa_pairs),
        allow_overwrite=allow_overwrite,
    )

    # Check if file exists
    if not allow_overwrite and output_path.exists():
        raise QAWriteError(f"Output file already exists (use allow_overwrite=True): {output_path}")

    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Serialize to dict
    qa_dicts = [qa.model_dump(mode="python") for qa in qa_pairs]

    # Write to temporary file first (atomic write)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=".tmp_qa_pairs_",
            suffix=".yaml",
            delete=False,
        ) as tmp_file:
            yaml.dump(
                qa_dicts,
                tmp_file,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
            tmp_path = Path(tmp_file.name)

        # Atomic rename
        tmp_path.replace(output_path)

        logger.info(
            "qa_pairs_written_successfully",
            output_path=str(output_path),
            count=len(qa_pairs),
            size_bytes=output_path.stat().st_size,
        )

    except (OSError, IOError, yaml.YAMLError) as e:
        # Clean up temp file if it exists
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()
        logger.error("qa_write_failed", output_path=str(output_path), error=str(e))
        raise QAWriteError(f"Failed to write QA pairs: {e}") from e


def write_qa_pairs(
    qa_pairs: list[QAPair],
    output_path: str | Path,
    output_format: str = "json",
    allow_overwrite: bool = False,
) -> None:
    """Write QA pairs to file with auto-detected or specified format.

    Args:
        qa_pairs: List of QAPair objects to write
        output_path: Path to output file
        output_format: Output format ("json" or "yaml"). If "auto", detect from extension
        allow_overwrite: If False, raise error if file exists

    Raises:
        ValueError: If format is invalid
        QAWriteError: If write fails
    """
    output_path = Path(output_path)

    # Auto-detect format from extension
    if output_format == "auto":
        suffix = output_path.suffix.lower()
        if suffix == ".json":
            output_format = "json"
        elif suffix in {".yaml", ".yml"}:
            output_format = "yaml"
        else:
            raise ValueError(f"Cannot auto-detect format from extension '{suffix}'. " "Specify format='json' or format='yaml'")

    # Validate empty list
    if not qa_pairs:
        logger.warning("empty_qa_pairs_list", output_path=str(output_path))

    # Write based on format
    if output_format == "json":
        write_qa_pairs_json(qa_pairs, output_path, allow_overwrite=allow_overwrite)
    elif output_format == "yaml":
        write_qa_pairs_yaml(qa_pairs, output_path, allow_overwrite=allow_overwrite)
    else:
        raise ValueError(f"Invalid format: {output_format}. Use 'json' or 'yaml'")
