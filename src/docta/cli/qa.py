"""QA generation commands."""

from __future__ import annotations

from pathlib import Path

import structlog
import typer

from docta.cli._error_handling import handle_qa_errors
from docta.utils.logging import configure_logging

logger = structlog.get_logger(__name__)
app = typer.Typer(help="QA generation from documentation diffs")


@app.command()
@handle_qa_errors
def generate(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    report_path: Path = typer.Argument(
        ...,
        help="Path to semantic diff report JSON file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    output_path: Path = typer.Argument(
        ...,
        help="Path to write QA pairs (JSON or YAML)",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to YAML configuration file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    testset_size: int | None = typer.Option(
        None,
        "--testset-size",
        "-n",
        help="Number of QA pairs to generate (overrides config)",
        min=1,
    ),
    num_documents: int | None = typer.Option(
        None,
        "--num-documents",
        "-d",
        help="Limit number of documents to process from report",
        min=1,
    ),
    output_format: str = typer.Option(
        "auto",
        "--format",
        "-f",
        help="Output format: json, yaml, or auto (detect from extension)",
    ),
    allow_overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Allow overwriting existing output file",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging",
    ),
) -> None:
    """Generate QA pairs from a semantic diff report.

    Processes modified/renamed documents from semantic diff analysis.

    Example:
        docta qa generate report.json output.json --config qa_config.yaml
    """
    configure_logging(verbose)

    # Lazy imports to handle optional QA dependencies
    from qa_generation.config.settings import (
        load_settings,
    )  # pylint: disable=import-outside-toplevel
    from qa_generation.pipeline import (  # pylint: disable=import-outside-toplevel
        generate_qa_from_report,
    )

    # Load settings
    overrides = {}
    if testset_size is not None:
        overrides["testset_size"] = testset_size

    settings = load_settings(yaml_path=config, **overrides)

    typer.echo("=" * 60)
    typer.echo("QA Generation Pipeline")
    typer.echo("=" * 60)
    typer.echo(f"Report:       {report_path}")
    typer.echo(f"Output:       {output_path}")
    typer.echo(f"Testset Size: {settings.testset_size}")
    typer.echo(f"LLM:          {settings.llm_provider}/{settings.llm_model}")
    typer.echo("=" * 60)
    typer.echo()

    # Run pipeline
    qa_pairs = generate_qa_from_report(
        report_path=report_path,
        output_path=output_path,
        settings=settings,
        output_format=output_format,
        allow_overwrite=allow_overwrite,
        num_documents=num_documents,
    )

    typer.echo()
    typer.secho(
        f"✓ Successfully generated {len(qa_pairs)} QA pairs",
        fg=typer.colors.GREEN,
        bold=True,
    )
    typer.secho(f"✓ Written to: {output_path}", fg=typer.colors.GREEN)


@app.command(name="from-added")
@handle_qa_errors
def from_added(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    delta_report_path: Path = typer.Argument(
        ...,
        help="Path to delta report JSON file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    output_path: Path = typer.Argument(
        ...,
        help="Path to write QA pairs (JSON or YAML)",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to YAML configuration file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    testset_size: int | None = typer.Option(
        None,
        "--testset-size",
        "-n",
        help="Number of QA pairs to generate (overrides config)",
        min=1,
    ),
    num_documents: int | None = typer.Option(
        None,
        "--num-documents",
        "-d",
        help="Limit number of added documents to process",
        min=1,
    ),
    output_format: str = typer.Option(
        "auto",
        "--format",
        "-f",
        help="Output format: json, yaml, or auto (detect from extension)",
    ),
    allow_overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Allow overwriting existing output file",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging",
    ),
) -> None:
    """Generate QA pairs from added documents in delta report.

    Processes newly added documents (net-new content) from the delta report.
    These documents don't have semantic diffs since they have no previous version.

    Example:
        docta qa from-added delta_report.json qa_pairs.json
    """
    configure_logging(verbose)

    # Lazy imports to handle optional QA dependencies
    from qa_generation.config.settings import (
        load_settings,
    )  # pylint: disable=import-outside-toplevel
    from qa_generation.pipeline import (  # pylint: disable=import-outside-toplevel
        generate_qa_from_delta_report,
    )

    # Load settings
    overrides = {}
    if testset_size is not None:
        overrides["testset_size"] = testset_size

    settings = load_settings(yaml_path=config, **overrides)

    typer.echo("=" * 60)
    typer.echo("QA Generation from Added Documents")
    typer.echo("=" * 60)
    typer.echo(f"Delta Report: {delta_report_path}")
    typer.echo(f"Output:       {output_path}")
    typer.echo(f"Testset Size: {settings.testset_size}")
    typer.echo(f"LLM:          {settings.llm_provider}/{settings.llm_model}")
    typer.echo("=" * 60)
    typer.echo()

    # Run pipeline
    qa_pairs = generate_qa_from_delta_report(
        delta_report_path=delta_report_path,
        output_path=output_path,
        settings=settings,
        output_format=output_format,
        allow_overwrite=allow_overwrite,
        num_documents=num_documents,
    )

    typer.echo()
    typer.secho(
        f"✓ Successfully generated {len(qa_pairs)} QA pairs from added documents",
        fg=typer.colors.GREEN,
        bold=True,
    )
    typer.secho(f"✓ Written to: {output_path}", fg=typer.colors.GREEN)


@app.command()
@handle_qa_errors
def unified(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-statements
    delta_report_path: Path = typer.Argument(
        ...,
        help="Path to delta report JSON file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    semantic_diff_report_path: Path = typer.Argument(
        ...,
        help="Path to semantic diff report JSON file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    output_path: Path = typer.Argument(
        ...,
        help="Path to write QA pairs (JSON or YAML)",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to YAML configuration file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    testset_size: int | None = typer.Option(
        None,
        "--testset-size",
        "-n",
        help="Number of QA pairs to generate (overrides config)",
        min=1,
    ),
    num_documents: int | None = typer.Option(
        None,
        "--num-documents",
        "-d",
        help="Limit total number of source documents to process",
        min=1,
    ),
    output_format: str = typer.Option(
        "auto",
        "--format",
        "-f",
        help="Output format: json, yaml, or auto (detect from extension)",
    ),
    allow_overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Allow overwriting existing output file",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging",
    ),
) -> None:
    """Generate QA pairs from both modified and added documents.

    This unified command processes:
    - Modified/renamed documents from semantic_diff_report.json
    - Added documents from delta_report.json

    Example:
        docta qa unified delta_report.json semantic_diff_report.json qa_pairs.json
    """
    configure_logging(verbose)

    # Lazy imports to handle optional QA dependencies
    from qa_generation.config.settings import (
        load_settings,
    )  # pylint: disable=import-outside-toplevel
    from qa_generation.pipeline import (  # pylint: disable=import-outside-toplevel
        generate_qa_from_both_sources,
    )

    # Load settings
    overrides = {}
    if testset_size is not None:
        overrides["testset_size"] = testset_size

    settings = load_settings(yaml_path=config, **overrides)

    typer.echo("=" * 60)
    typer.echo("Unified QA Generation (Modified + Added)")
    typer.echo("=" * 60)
    typer.echo(f"Delta Report:         {delta_report_path}")
    typer.echo(f"Semantic Diff Report: {semantic_diff_report_path}")
    typer.echo(f"Output:               {output_path}")
    typer.echo(f"Testset Size:         {settings.testset_size}")
    typer.echo(f"LLM:                  {settings.llm_provider}/{settings.llm_model}")
    typer.echo("=" * 60)
    typer.echo()

    # Run pipeline
    qa_pairs = generate_qa_from_both_sources(
        delta_report_path=delta_report_path,
        semantic_diff_report_path=semantic_diff_report_path,
        output_path=output_path,
        settings=settings,
        output_format=output_format,
        allow_overwrite=allow_overwrite,
        num_documents=num_documents,
    )

    typer.echo()
    typer.secho(
        f"✓ Successfully generated {len(qa_pairs)} QA pairs from both sources",
        fg=typer.colors.GREEN,
        bold=True,
    )
    typer.secho(f"✓ Written to: {output_path}", fg=typer.colors.GREEN)


@app.command()
def version() -> None:
    """Show version information."""
    typer.echo("docta qa version 0.1.0")
    typer.echo("Part of docta project")
