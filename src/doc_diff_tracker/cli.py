"""Command-line interface for doc-diff-tracker."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from doc_diff_tracker.output.reporting import (
    summarize_report,
    write_report,
    summarize_html_diff_report,
    write_html_diff_report,
)
from doc_diff_tracker.utils.security import (
    SecurityError,
    validate_output_path,
)
from doc_diff_tracker.utils.scanner import scan_and_compare
from doc_diff_tracker.utils.cli_helpers import (
    validate_pipeline_params,
    validate_common_inputs,
    execute_manifest_comparison,
)

app = typer.Typer(help="Minimal documentation delta proof of concept")


@app.command()
def compare(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    old_root: str = typer.Option(..., help="Path to the older corpus root"),
    new_root: str = typer.Option(..., help="Path to the newer corpus root"),
    old_version: str = typer.Option("9", help="Label for older corpus version"),
    new_version: str = typer.Option("10", help="Label for newer corpus version"),
    output: str = typer.Option(
        "artifacts/report.json", help="Path to write JSON report"
    ),
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
        # Validate all inputs
        old_version, new_version, rename_threshold = validate_pipeline_params(
            old_version, new_version, rename_threshold
        )
        old_root_path, new_root_path = validate_common_inputs(
            old_root, new_root, allow_symlinks
        )
        output_path = validate_output_path(
            output,
            allowed_extensions={".json"},
            allow_overwrite=allow_overwrite,
        )

        # Execute comparison
        report = execute_manifest_comparison(
            old_root_path,
            new_root_path,
            old_version,
            new_version,
            rename_threshold,
            allow_symlinks,
        )

        # Write and display results
        write_report(report, str(output_path))
        typer.echo(f"✓ Wrote report to {output_path}")
        typer.echo(summarize_report(report))

    except SecurityError as e:
        typer.echo(f"Security validation failed: {e}", err=True)
        sys.exit(1)
    except (OSError, ValueError, RuntimeError) as e:
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)


@app.command()
def scan(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    report: str = typer.Option(..., help="Path to delta report JSON file"),
    old_root: str = typer.Option(..., help="Path to the older corpus root"),
    new_root: str = typer.Option(..., help="Path to the newer corpus root"),
    output: str = typer.Option(
        "artifacts/html_diff_report.json", help="Path to write JSON report"
    ),
    include_modified: bool = typer.Option(
        True, help="Include modified documents in comparison"
    ),
    include_renamed: bool = typer.Option(
        True, help="Include renamed candidates in comparison"
    ),
    max_docs: int | None = typer.Option(
        None, help="Maximum number of documents to process (None for all)"
    ),
    allow_overwrite: bool = typer.Option(
        False, help="Allow overwriting existing output file"
    ),
    allow_symlinks: bool = typer.Option(
        False, help="Allow processing symlinked files and directories"
    ),
) -> None:
    """
    Scan a delta report and compare HTML documents using semantic content extraction.

    This tool reads a delta report JSON file, identifies modified and renamed
    documents, and performs semantic comparison by extracting and comparing content
    blocks (headings, text, code, tables, lists). This approach ignores cosmetic
    HTML changes and focuses on actual content changes.
    """
    try:
        # Validate max_docs parameter
        if max_docs is not None and max_docs <= 0:
            raise ValueError("max_docs must be positive")

        # Validate input paths
        typer.echo("Validating input paths...")
        report_path = Path(report)
        if not report_path.exists():
            raise ValueError(f"Report file not found: {report}")
        if not report_path.is_file():
            raise ValueError(f"Report path is not a file: {report}")

        old_root_path, new_root_path = validate_common_inputs(
            old_root, new_root, allow_symlinks
        )

        output_path = validate_output_path(
            output,
            allowed_extensions={".json"},
            allow_overwrite=allow_overwrite,
        )

        # Scan and compare
        typer.echo(f"Scanning delta report from {report_path}...")
        html_diff_report = scan_and_compare(
            report_path=report_path,
            old_root=old_root_path,
            new_root=new_root_path,
            include_modified=include_modified,
            include_renamed=include_renamed,
            max_files=max_docs,
        )

        # Write report
        write_html_diff_report(html_diff_report, str(output_path))
        typer.echo(f"✓ Wrote HTML diff report to {output_path}")
        typer.echo(summarize_html_diff_report(html_diff_report))

    except SecurityError as e:
        typer.echo(f"Security validation failed: {e}", err=True)
        sys.exit(1)
    except (OSError, ValueError, RuntimeError) as e:
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)


@app.command()
def full_diff(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    old_root: str = typer.Option(..., help="Path to the older corpus root"),
    new_root: str = typer.Option(..., help="Path to the newer corpus root"),
    old_version: str = typer.Option("9", help="Label for older corpus version"),
    new_version: str = typer.Option("10", help="Label for newer corpus version"),
    output_dir: str = typer.Option(
        "artifacts", help="Directory to write output reports"
    ),
    rename_threshold: float = typer.Option(
        85.0, help="RapidFuzz threshold for rename candidates (0-100)"
    ),
    include_modified: bool = typer.Option(
        True, help="Include modified documents in semantic comparison"
    ),
    include_renamed: bool = typer.Option(
        True, help="Include renamed candidates in semantic comparison"
    ),
    max_docs: int | None = typer.Option(
        None,
        help="Maximum number of documents to process in semantic scan (None for all)",
    ),
    allow_overwrite: bool = typer.Option(
        False, help="Allow overwriting existing output files"
    ),
    allow_symlinks: bool = typer.Option(
        False, help="Allow processing symlinked files and directories"
    ),
) -> None:
    """
    Run full pipeline: compare manifests and perform semantic diff in one command.

    This combines the 'compare' and 'scan' commands into a single workflow:
    1. Builds manifests and generates delta report (identifies changed files)
    2. Performs semantic content extraction and comparison on changed documents
    """
    try:
        # Validate all inputs
        old_version, new_version, rename_threshold = validate_pipeline_params(
            old_version, new_version, rename_threshold
        )
        if max_docs is not None and max_docs <= 0:
            raise ValueError("max_docs must be positive")
        old_root_path, new_root_path = validate_common_inputs(
            old_root, new_root, allow_symlinks
        )

        # Create output directory
        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True)

        # Define and validate output paths
        delta_report_path = validate_output_path(
            str(output_dir_path / "delta_report.json"),
            allowed_extensions={".json"},
            allow_overwrite=allow_overwrite,
        )
        semantic_report_path = validate_output_path(
            str(output_dir_path / "semantic_diff_report.json"),
            allowed_extensions={".json"},
            allow_overwrite=allow_overwrite,
        )

        # ===== Stage 1: Compare Manifests =====
        typer.echo("\n=== Stage 1: Building Manifests and Comparing ===")
        delta_report = execute_manifest_comparison(
            old_root_path,
            new_root_path,
            old_version,
            new_version,
            rename_threshold,
            allow_symlinks,
        )

        # Write delta report
        write_report(delta_report, str(delta_report_path))
        typer.echo(f"✓ Wrote delta report to {delta_report_path}")
        typer.echo(summarize_report(delta_report))

        # ===== Stage 2: Semantic Comparison =====
        typer.echo("\n=== Stage 2: Semantic Content Comparison ===")
        typer.echo("Scanning delta report and performing semantic diff...")

        html_diff_report = scan_and_compare(
            report_path=delta_report_path,
            old_root=old_root_path,
            new_root=new_root_path,
            include_modified=include_modified,
            include_renamed=include_renamed,
            max_files=max_docs,
        )

        # Write semantic diff report
        write_html_diff_report(html_diff_report, str(semantic_report_path))
        typer.echo(f"✓ Wrote semantic diff report to {semantic_report_path}")
        typer.echo(summarize_html_diff_report(html_diff_report))

        typer.echo("\n=== Pipeline Complete ===")
        typer.echo(f"Delta report: {delta_report_path}")
        typer.echo(f"Semantic diff report: {semantic_report_path}")

    except SecurityError as e:
        typer.echo(f"Security validation failed: {e}", err=True)
        sys.exit(1)
    except (OSError, ValueError, RuntimeError) as e:
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    app()
