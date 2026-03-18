"""Helper functions for CLI commands to reduce duplication."""

from __future__ import annotations

from pathlib import Path

import typer

from doc_diff_tracker.models.models import DeltaReport
from doc_diff_tracker.utils.inventory import build_manifest
from doc_diff_tracker.compare.lineage import compare_manifests
from doc_diff_tracker.utils.security import (
    validate_float_parameter,
    validate_input_directory,
    validate_version_string,
)


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
    typer.echo(f"Building manifest for {old_version} from {old_root_path}...")
    old_docs = build_manifest(
        str(old_root_path),
        old_version,
        allow_symlinks=allow_symlinks,
    )

    typer.echo(f"Building manifest for {new_version} from {new_root_path}...")
    new_docs = build_manifest(
        str(new_root_path),
        new_version,
        allow_symlinks=allow_symlinks,
    )

    typer.echo("Comparing manifests...")
    comparison = compare_manifests(
        old_docs=old_docs,
        new_docs=new_docs,
        rename_threshold=rename_threshold,
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
