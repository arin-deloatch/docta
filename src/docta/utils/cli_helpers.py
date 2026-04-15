"""Helper functions for CLI commands to reduce duplication."""

from __future__ import annotations

from pathlib import Path

import structlog
import typer

from docta.models.models import DeltaReport
from docta.utils.inventory import build_manifest
from docta.compare.lineage import compare_manifests
from docta.utils.security import (
    validate_float_parameter,
    validate_input_directory,
    validate_version_string,
)

logger = structlog.get_logger(__name__)


def validate_pipeline_params(
    old_version: str,
    new_version: str,
    rename_threshold: float,
) -> tuple[str, str, float]:
    """
    Validate pipeline parameters used across commands.

    Args:
        old_version: Label for older corpus version
        new_version: Label for newer corpus version
        rename_threshold: RapidFuzz threshold for rename candidates (0-100)

    Returns:
        Tuple of (validated_old_version, validated_new_version, validated_threshold)

    Raises:
        ValueError: If parameters are invalid
    """
    old_version = validate_version_string(old_version)
    new_version = validate_version_string(new_version)
    rename_threshold = validate_float_parameter(
        rename_threshold,
        name="rename_threshold",
        min_val=0.0,
        max_val=100.0,
    )

    return old_version, new_version, rename_threshold


def validate_common_inputs(
    old_root: str,
    new_root: str,
    allow_symlinks: bool,
) -> tuple[Path, Path]:
    """
    Validate common input directories.

    Args:
        old_root: Path to older corpus root
        new_root: Path to newer corpus root
        allow_symlinks: Allow processing symlinked files/directories

    Returns:
        Tuple of (old_root_path, new_root_path)

    Raises:
        SecurityError: If validation fails
        ValueError: If paths are invalid
    """
    logger.info("validating_input_directories", old_root=old_root, new_root=new_root)
    typer.echo("Validating input directories...")
    old_root_path = validate_input_directory(
        old_root,
        must_exist=True,
        allow_symlinks=allow_symlinks,
    )
    new_root_path = validate_input_directory(
        new_root,
        must_exist=True,
        allow_symlinks=allow_symlinks,
    )
    logger.info("input_directories_validated")
    return old_root_path, new_root_path


def execute_manifest_comparison(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    old_root_path: Path,
    new_root_path: Path,
    old_version: str,
    new_version: str,
    rename_threshold: float,
    allow_symlinks: bool,
) -> DeltaReport:
    """
    Execute manifest building and comparison.

    Args:
        old_root_path: Path to older corpus root
        new_root_path: Path to newer corpus root
        old_version: Label for older corpus version
        new_version: Label for newer corpus version
        rename_threshold: RapidFuzz threshold for rename candidates
        allow_symlinks: Allow processing symlinked files/directories

    Returns:
        DeltaReport with comparison results

    Raises:
        OSError: If manifest building fails
        RuntimeError: If comparison fails
    """
    logger.info("building_old_manifest", version=old_version, path=str(old_root_path))
    typer.echo(f"Building manifest for {old_version} from {old_root_path}...")
    old_docs = build_manifest(
        str(old_root_path),
        old_version,
        allow_symlinks=allow_symlinks,
    )
    logger.info("old_manifest_built", doc_count=len(old_docs))

    logger.info("building_new_manifest", version=new_version, path=str(new_root_path))
    typer.echo(f"Building manifest for {new_version} from {new_root_path}...")
    new_docs = build_manifest(
        str(new_root_path),
        new_version,
        allow_symlinks=allow_symlinks,
    )
    logger.info("new_manifest_built", doc_count=len(new_docs))

    logger.info("comparing_manifests", rename_threshold=rename_threshold)
    typer.echo("Comparing manifests...")
    comparison = compare_manifests(
        old_docs=old_docs,
        new_docs=new_docs,
        rename_threshold=rename_threshold,
    )
    logger.info(
        "manifests_compared",
        unchanged=len(comparison.unchanged),
        modified=len(comparison.modified),
        renamed_candidates=len(comparison.renamed_candidates),
        removed=len(comparison.removed),
        added=len(comparison.added),
    )

    return DeltaReport(
        old_version=old_version,
        new_version=new_version,
        unchanged=comparison.unchanged,
        modified=comparison.modified,
        renamed_candidates=comparison.renamed_candidates,
        removed=comparison.removed,
        added=comparison.added,
    )
