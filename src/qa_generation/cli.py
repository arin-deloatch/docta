"""CLI for QA generation from semantic diff reports."""

from __future__ import annotations

from pathlib import Path

import structlog
import typer

from doc_diff_tracker.utils.logging import configure_logging
from qa_generation.config.settings import load_settings
from qa_generation.generators.base import (
    ConfigurationError,
    LLMError,
    QAGenerationError,
)
from qa_generation.pipeline import (
    generate_qa_from_both_sources,
    generate_qa_from_delta_report,
    generate_qa_from_report,
)

app = typer.Typer(
    name="qa-generator",
    help="Generate QA pairs from semantic diff reports using RAGAS",
    add_completion=False,
)
logger = structlog.get_logger(__name__)


@app.command()
def generate(
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
    format: str = typer.Option(
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

    Example:
        qa-generator generate report.json output.json --config qa_config.yaml
    """
    configure_logging(verbose)

    try:
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
            output_format=format,
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

    except FileNotFoundError as e:
        typer.secho(f"Error: File not found: {e}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)

    except ValueError as e:
        typer.secho(f"Error: Invalid input: {e}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)

    except ConfigurationError as e:
        typer.secho(f"Configuration Error: {e}", fg=typer.colors.RED, bold=True)
        typer.secho(
            "\nHint: Check your config file and API keys (e.g., QA_OPENAI_API_KEY)",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(1)

    except LLMError as e:
        typer.secho(f"LLM API Error: {e}", fg=typer.colors.RED, bold=True)
        typer.secho(
            "\nHint: Check your API key, rate limits, and quota",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(1)

    except QAGenerationError as e:
        typer.secho(f"Generation Error: {e}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)

    except KeyboardInterrupt:
        typer.secho("\nInterrupted by user", fg=typer.colors.YELLOW)
        raise typer.Exit(130)

    except Exception as e:
        typer.secho(f"Unexpected Error: {e}", fg=typer.colors.RED, bold=True)
        logger.exception("unexpected_error")
        raise typer.Exit(1)


@app.command()
def generate_from_added(
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
    format: str = typer.Option(
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

    This command processes newly added documents (net-new content)
    from the delta report. These documents don't have semantic diffs
    since they have no previous version.

    Example:
        qa-generator generate-from-added delta_report.json qa_pairs.json
    """
    configure_logging(verbose)

    try:
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
            output_format=format,
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

    except FileNotFoundError as e:
        typer.secho(f"Error: File not found: {e}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)

    except ValueError as e:
        typer.secho(f"Error: Invalid input: {e}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)

    except ConfigurationError as e:
        typer.secho(f"Configuration Error: {e}", fg=typer.colors.RED, bold=True)
        typer.secho(
            "\nHint: Check your config file and API keys (e.g., QA_OPENAI_API_KEY)",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(1)

    except LLMError as e:
        typer.secho(f"LLM API Error: {e}", fg=typer.colors.RED, bold=True)
        typer.secho(
            "\nHint: Check your API key, rate limits, and quota",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(1)

    except QAGenerationError as e:
        typer.secho(f"Generation Error: {e}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)

    except KeyboardInterrupt:
        typer.secho("\nInterrupted by user", fg=typer.colors.YELLOW)
        raise typer.Exit(130)

    except Exception as e:
        typer.secho(f"Unexpected Error: {e}", fg=typer.colors.RED, bold=True)
        logger.exception("unexpected_error")
        raise typer.Exit(1)


@app.command()
def generate_unified(
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
    format: str = typer.Option(
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
        qa-generator generate-unified delta_report.json semantic_diff_report.json qa_pairs.json
    """
    configure_logging(verbose)

    try:
        # Load settings
        overrides = {}
        if testset_size is not None:
            overrides["testset_size"] = testset_size

        settings = load_settings(yaml_path=config, **overrides)

        typer.echo("=" * 60)
        typer.echo("Unified QA Generation (Modified + Added)")
        typer.echo("=" * 60)
        typer.echo(f"Delta Report:        {delta_report_path}")
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
            output_format=format,
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

    except FileNotFoundError as e:
        typer.secho(f"Error: File not found: {e}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)

    except ValueError as e:
        typer.secho(f"Error: Invalid input: {e}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)

    except ConfigurationError as e:
        typer.secho(f"Configuration Error: {e}", fg=typer.colors.RED, bold=True)
        typer.secho(
            "\nHint: Check your config file and API keys (e.g., OPENAI_API_KEY)",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(1)

    except LLMError as e:
        typer.secho(f"LLM API Error: {e}", fg=typer.colors.RED, bold=True)
        typer.secho(
            "\nHint: Check your API key, rate limits, and quota",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(1)

    except QAGenerationError as e:
        typer.secho(f"Generation Error: {e}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)

    except KeyboardInterrupt:
        typer.secho("\nInterrupted by user", fg=typer.colors.YELLOW)
        raise typer.Exit(130)

    except Exception as e:
        typer.secho(f"Unexpected Error: {e}", fg=typer.colors.RED, bold=True)
        logger.exception("unexpected_error")
        raise typer.Exit(1)


@app.command()
def version() -> None:
    """Show version information."""
    typer.echo("qa-generator version 0.1.0")
    typer.echo("Part of doc-diff-tracker project")


if __name__ == "__main__":
    app()
