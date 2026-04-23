"""Shared error handling decorators for CLI commands."""

# pylint: disable=duplicate-code

from __future__ import annotations

import functools
import sys
from typing import Any, Callable, TypeVar

import structlog
import typer

F = TypeVar("F", bound=Callable[..., Any])

logger = structlog.get_logger(__name__)


def handle_cli_errors(func: F) -> F:
    """Decorator for diff/daemon command error handling.

    Catches common exceptions and provides user-friendly error messages
    with appropriate exit codes.

    Handles:
    - SecurityError: Path validation failures
    - FileNotFoundError: Missing input files
    - OSError, ValueError, RuntimeError: General errors
    - KeyboardInterrupt: User cancellation
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except FileNotFoundError as e:
            logger.error(f"{func.__name__}_failed", error_type="file_not_found", error=str(e))
            typer.echo(f"Error: {e}", err=True)
            sys.exit(1)
        except KeyboardInterrupt:
            logger.info(f"{func.__name__}_interrupted_by_user")
            typer.echo("\n✓ Stopped by user")
            sys.exit(0)
        except Exception as e:  # pylint: disable=broad-exception-caught
            # Top-level CLI handler needs to catch all exceptions
            logger.error(f"{func.__name__}_failed", error_type=type(e).__name__, error=str(e))
            typer.echo(f"Error: {e}", err=True)
            sys.exit(1)

    return wrapper  # type: ignore[return-value]


def handle_qa_errors(func: F) -> F:
    """Decorator for QA generation command error handling.

    Provides specialized error messages for QA generation failures,
    including LLM API errors and configuration issues.

    Handles:
    - FileNotFoundError: Missing input files
    - ValueError: Invalid input parameters
    - ConfigurationError: Configuration/API key issues
    - LLMError: LLM API failures
    - QAGenerationError: Generation failures
    - KeyboardInterrupt: User cancellation
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except FileNotFoundError as e:
            typer.secho(f"Error: File not found: {e}", fg=typer.colors.RED, bold=True)
            raise typer.Exit(1)
        except ValueError as e:
            typer.secho(f"Error: Invalid input: {e}", fg=typer.colors.RED, bold=True)
            raise typer.Exit(1)
        except ImportError as e:
            # Handle missing QA dependencies gracefully
            typer.secho(f"Error: Missing QA dependencies: {e}", fg=typer.colors.RED, bold=True)
            typer.secho(
                "\nQA generation requires additional dependencies.",
                fg=typer.colors.YELLOW,
            )
            typer.secho("Install with: uv sync --extra qa", fg=typer.colors.YELLOW)
            raise typer.Exit(1)
        except KeyboardInterrupt as exc:
            typer.secho("\nInterrupted by user", fg=typer.colors.YELLOW)
            raise typer.Exit(130) from exc
        except Exception as e:
            # Try to catch specialized QA errors if dependencies are available
            try:
                from qa_generation.generators.base import (  # pylint: disable=import-outside-toplevel
                    ConfigurationError,
                    LLMError,
                    QAGenerationError,
                )

                if isinstance(e, ConfigurationError):  # pylint: disable=no-else-raise
                    typer.secho(f"Configuration Error: {e}", fg=typer.colors.RED, bold=True)
                    typer.secho(
                        "\nHint: Check your config file and API keys (e.g., OPENAI_API_KEY)",
                        fg=typer.colors.YELLOW,
                    )
                    raise typer.Exit(1)
                elif isinstance(e, LLMError):
                    typer.secho(f"LLM API Error: {e}", fg=typer.colors.RED, bold=True)
                    typer.secho(
                        "\nHint: Check your API key, rate limits, and quota",
                        fg=typer.colors.YELLOW,
                    )
                    raise typer.Exit(1)
                elif isinstance(e, QAGenerationError):
                    typer.secho(f"Generation Error: {e}", fg=typer.colors.RED, bold=True)
                    raise typer.Exit(1)
            except ImportError:
                # QA dependencies not available, fall through to generic handler
                pass

            typer.secho(f"Unexpected Error: {e}", fg=typer.colors.RED, bold=True)
            logger.exception("unexpected_error")
            raise typer.Exit(1)

    return wrapper  # type: ignore[return-value]
