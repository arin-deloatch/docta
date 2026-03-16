"""Command-line interface for doc-diff-tracker."""

from __future__ import annotations

import sys

import typer

from .utils.inventory import build_manifest
from .compare.lineage import compare_manifests
from .models.models import DeltaReport
from .output.reporting import summarize_report, write_report
from .utils.security import (
    SecurityError,
    validate_float_parameter,
    validate_input_directory,
    validate_output_path,
    validate_version_string,
)

app = typer.Typer(help="Minimal documentation delta proof of concept")


@app.command()
def compare(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    old_root: str = typer.Option(..., help="Path to the older corpus root"),
    new_root: str = typer.Option(..., help="Path to the newer corpus root"),
    old_version: str = typer.Option("9", help="Label for older corpus version"),
    new_version: str = typer.Option("10", help="Label for newer corpus version"),
    output: str = typer.Option("report.json", help="Path to write JSON report"),
    rename_threshold: float = typer.Option(
        85.0, help="RapidFuzz threshold for rename candidates (0-100)"
    ),
    allow_overwrite: bool = typer.Option(
        False, help="Allow overwriting existing output file"
    ),
    allow_symlinks: bool = typer.Option(
        False, help="Allow processing symlinked files and directories"
    ),
) -> None:
    """
    Compare two documentation corpus versions and generate a delta report.

    This tool scans HTML documentation directories, identifies changes between
    versions, and produces a structured JSON report.
    """
    try:
        # Validate version strings
        old_version = validate_version_string(old_version)
        new_version = validate_version_string(new_version)

        # Validate rename threshold parameter
        rename_threshold = validate_float_parameter(
            rename_threshold,
            name="rename_threshold",
            min_val=0.0,
            max_val=100.0,
        )

        # Validate input directories
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

        # Validate output path
        output_path = validate_output_path(
            output,
            allowed_extensions={".json"},
            allow_overwrite=allow_overwrite,
        )

        # Build manifests with validated paths
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

        # Compare manifests
        typer.echo("Comparing manifests...")
        unchanged, modified, renamed_candidates, removed, added = compare_manifests(
            old_docs=old_docs,
            new_docs=new_docs,
            rename_threshold=rename_threshold,
        )

        # Generate report
        report = DeltaReport(
            old_version=old_version,
            new_version=new_version,
            unchanged=unchanged,
            modified=modified,
            renamed_candidates=renamed_candidates,
            removed=removed,
            added=added,
        )

        # Write report
        write_report(report, str(output_path))
        typer.echo(f"✓ Wrote report to {output_path}")
        typer.echo(summarize_report(report))

    except SecurityError as e:
        typer.echo(f"Security validation failed: {e}", err=True)
        sys.exit(1)
    except (OSError, ValueError, RuntimeError) as e:
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    app()
