"""Command-line interface for doc-diff-tracker."""

from __future__ import annotations

import sys
from pathlib import Path

import structlog
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
from doc_diff_tracker.utils.logging import configure_logging

logger = structlog.get_logger(__name__)
app = typer.Typer(help="Minimal documentation delta proof of concept")


@app.command()
def compare(
    *,
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
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging (DEBUG level)"
    ),
) -> None:
    """
    Compare two documentation corpus versions and generate a delta report.

    This tool scans HTML documentation directories, identifies changes between
    versions, and produces a structured JSON report.
    """
    configure_logging(verbose)

    try:
        logger.info(
            "compare_command_started",
            old_root=old_root,
            new_root=new_root,
            old_version=old_version,
            new_version=new_version,
        )

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

        logger.info("compare_command_completed", output=str(output_path))

    except SecurityError as e:
        logger.error("compare_command_failed", error_type="security", error=str(e))
        typer.echo(f"Security validation failed: {e}", err=True)
        sys.exit(1)
    except (OSError, ValueError, RuntimeError) as e:
        logger.error(
            "compare_command_failed", error_type=type(e).__name__, error=str(e)
        )
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)


@app.command()
def scan(  # pylint: disable=too-many-locals
    *,
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
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging (DEBUG level)"
    ),
) -> None:
    """
    Scan a delta report and compare HTML documents using semantic content extraction.

    This tool reads a delta report JSON file, identifies modified and renamed
    documents, and performs semantic comparison by extracting and comparing content
    blocks (headings, text, code, tables, lists). This approach ignores cosmetic
    HTML changes and focuses on actual content changes.
    """
    configure_logging(verbose)

    try:
        logger.info(
            "scan_command_started",
            report=report,
            old_root=old_root,
            new_root=new_root,
            max_docs=max_docs,
        )

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

        logger.info("scan_command_completed", output=str(output_path))

    except SecurityError as e:
        logger.error("scan_command_failed", error_type="security", error=str(e))
        typer.echo(f"Security validation failed: {e}", err=True)
        sys.exit(1)
    except (OSError, ValueError, RuntimeError) as e:
        logger.error("scan_command_failed", error_type=type(e).__name__, error=str(e))
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)


@app.command()
def full_diff(  # pylint: disable=too-many-locals
    *,
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
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging (DEBUG level)"
    ),
) -> None:
    """
    Run full pipeline: compare manifests and perform semantic diff in one command.

    This combines the 'compare' and 'scan' commands into a single workflow:
    1. Builds manifests and generates delta report (identifies changed files)
    2. Performs semantic content extraction and comparison on changed documents
    """
    configure_logging(verbose)

    try:
        logger.info(
            "full_diff_command_started",
            old_root=old_root,
            new_root=new_root,
            old_version=old_version,
            new_version=new_version,
            output_dir=output_dir,
        )

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
        logger.info("stage1_started", stage="manifest_comparison")
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
        logger.info("stage1_completed", output=str(delta_report_path))

        # ===== Stage 2: Semantic Comparison =====
        logger.info("stage2_started", stage="semantic_comparison")
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
        logger.info("stage2_completed", output=str(semantic_report_path))

        typer.echo("\n=== Pipeline Complete ===")
        typer.echo(f"Delta report: {delta_report_path}")
        typer.echo(f"Semantic diff report: {semantic_report_path}")

        logger.info("full_diff_command_completed")

    except SecurityError as e:
        logger.error("full_diff_command_failed", error_type="security", error=str(e))
        typer.echo(f"Security validation failed: {e}", err=True)
        sys.exit(1)
    except (OSError, ValueError, RuntimeError) as e:
        logger.error(
            "full_diff_command_failed", error_type=type(e).__name__, error=str(e)
        )
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)


@app.command("daemon-start")
def daemon_start(
    *,
    config: str = typer.Option(
        "config/graphql_polling.yaml",
        help="Path to GraphQL polling configuration",
    ),
    foreground: bool = typer.Option(
        False,
        "--foreground",
        "-f",
        help="Run in foreground (don't daemonize)",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging (DEBUG level)"
    ),
) -> None:
    """Start the GraphQL polling daemon service.

    Polls a GraphQL API for documentation changes and automatically runs
    the diff + QA generation pipeline when changes are detected.

    Configuration file specifies:
    - GraphQL endpoint and queries
    - OAuth authentication (via environment variables)
    - Polling interval and retry behavior
    - Pipeline settings (output directories, QA generation, etc.)

    Environment variables required:
    - GRAPHQL_CLIENT_ID: OAuth client ID
    - GRAPHQL_CLIENT_SECRET: OAuth client secret
    - GRAPHQL_TOKEN_URL: OAuth token endpoint URL
    - APOLLOGRAPHQL_CLIENT_NAME: Apollo client name header
    """
    configure_logging(verbose)

    try:
        from pathlib import Path

        from doc_diff_tracker.graphql.client import GraphQLClient
        from doc_diff_tracker.graphql.config import load_graphql_settings
        from doc_diff_tracker.graphql.fetcher import ContentFetcher
        from doc_diff_tracker.graphql.pipeline import PipelineRunner
        from doc_diff_tracker.graphql.scheduler import PollingScheduler
        from doc_diff_tracker.graphql.state import StateManager

        logger.info("daemon_start_command", config=config, foreground=foreground)
        typer.echo("Starting GraphQL polling daemon...")
        typer.echo(f"Configuration: {config}")

        # Load configuration
        config_path = Path(config)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config}")

        settings = load_graphql_settings(config_path)

        typer.echo(
            f"Loaded {len(settings.graphql.query_sets)} query set(s), "
            f"polling interval: {settings.graphql.polling.interval_minutes} minutes"
        )

        # Initialize components
        logger.info("initializing_graphql_client")
        # Use cert_path for SSL verification if provided, otherwise use verify boolean
        ssl_verify: bool | str = (
            settings.graphql.ssl.cert_path
            or settings.graphql_cert_path
            or settings.graphql.ssl.verify
        )

        client = GraphQLClient(
            endpoint=settings.graphql.endpoint,
            api_scope=settings.graphql.api_scope,
            client_id=settings.graphql_client_id,
            client_secret=settings.graphql_client_secret,
            token_url=settings.graphql_token_url,
            apollographql_client_name=settings.apollographql_client_name,
            apollographql_client_version=settings.graphql.apollographql_client_version,
            ssl_verify=ssl_verify,
            timeout=settings.graphql.polling.timeout_seconds,
            retry_attempts=settings.graphql.polling.retry_attempts,
        )

        logger.info("initializing_content_fetcher")
        download_dir = Path(settings.content.download_dir)
        fetcher = ContentFetcher(
            get_access_token=client.get_token_for_content_fetching(),
            download_dir=download_dir,
            max_size_mb=settings.content.max_file_size_mb,
            timeout=settings.content.timeout_seconds,
            max_workers=10,  # Default, overridden per query set
            ssl_verify=ssl_verify,
        )

        logger.info("initializing_state_manager")
        state_file = Path(settings.state.file_path)
        state_manager = StateManager(
            state_file=state_file,
            backup_enabled=settings.state.backup_enabled,
            backup_count=settings.state.backup_count,
            prune_removed=settings.state.prune_removed_documents,
            cleanup_files=settings.state.cleanup_old_files,
        )

        logger.info("initializing_pipeline_runner")
        pipeline_runner = PipelineRunner(state_manager)

        logger.info("initializing_scheduler")
        scheduler = PollingScheduler(
            settings=settings,
            client=client,
            fetcher=fetcher,
            state_manager=state_manager,
            pipeline_runner=pipeline_runner,
        )

        # Run scheduler
        if foreground:
            typer.echo("Running in foreground (Ctrl+C to stop)...")
            logger.info("starting_foreground_polling")
            scheduler.run_forever()
        else:
            # For background mode, we'd typically use a process manager like systemd
            # For now, just run in foreground and advise user to use systemd/Docker
            typer.echo(
                "Background daemonization not implemented - use systemd or Docker"
            )
            typer.echo("Running in foreground mode instead (Ctrl+C to stop)...")
            logger.info("starting_foreground_polling_fallback")
            scheduler.run_forever()

        logger.info("daemon_stopped")

    except FileNotFoundError as e:
        logger.error("daemon_start_failed", error_type="file_not_found", error=str(e))
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("daemon_interrupted_by_user")
        typer.echo("\n✓ Daemon stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error("daemon_start_failed", error_type=type(e).__name__, error=str(e))
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)


@app.command("daemon-stop")
def daemon_stop() -> None:
    """Stop the running GraphQL polling daemon.

    This command is a placeholder for future implementation.
    Currently, use Ctrl+C to stop a foreground daemon, or
    `systemctl stop doc-diff-graphql-poller` for systemd service.
    """
    typer.echo("Daemon stop not implemented - use:")
    typer.echo("  - Ctrl+C for foreground daemon")
    typer.echo("  - systemctl stop doc-diff-graphql-poller for systemd")
    typer.echo("  - docker-compose down for Docker")


@app.command("daemon-status")
def daemon_status(
    *,
    config: str = typer.Option(
        "config/graphql_polling.yaml",
        help="Path to GraphQL polling configuration",
    ),
) -> None:
    """Check status of GraphQL polling daemon.

    Reads the state file and displays polling statistics.
    """
    try:
        from pathlib import Path

        from doc_diff_tracker.graphql.config import load_graphql_settings
        from doc_diff_tracker.graphql.state import StateManager

        # Load configuration to get state file path
        config_path = Path(config)
        if not config_path.exists():
            typer.echo(f"Configuration file not found: {config}", err=True)
            sys.exit(1)

        settings = load_graphql_settings(config_path)
        state_file = Path(settings.state.file_path)

        if not state_file.exists():
            typer.echo("No state file found - daemon has never run")
            typer.echo(f"Expected state file: {state_file}")
            sys.exit(0)

        # Load and display state
        state_manager = StateManager(
            state_file=state_file,
            backup_enabled=False,  # Read-only, no backups needed
        )
        state = state_manager.load_state()

        typer.echo("=== GraphQL Polling Daemon Status ===\n")
        typer.echo(f"State file: {state_file}")
        typer.echo(f"Last updated: {state.last_updated}")
        typer.echo(f"Total query sets: {len(state.query_sets)}\n")

        for query_set_name, query_state in state.query_sets.items():
            typer.echo(f"Query Set: {query_set_name}")
            typer.echo(f"  Last poll: {query_state.last_poll or 'Never'}")
            typer.echo(f"  Last success: {query_state.last_success or 'Never'}")
            typer.echo(f"  Total documents: {query_state.stats.total_documents}")
            typer.echo(f"  Total polls: {query_state.stats.total_polls}")
            typer.echo(
                f"  Documents with changes: {query_state.stats.documents_with_changes}"
            )
            typer.echo(
                f"  Total pipeline runs: {query_state.stats.total_pipeline_runs}"
            )
            typer.echo()

    except Exception as e:
        typer.echo(f"Error reading daemon status: {e}", err=True)
        sys.exit(1)


@app.command("daemon-run-once")
def daemon_run_once(
    *,
    config: str = typer.Option(..., help="Path to GraphQL polling configuration"),
    query_set: str | None = typer.Option(
        None, "--query-set", help="Optional: specific query set to poll"
    ),
    force_new: bool = typer.Option(
        False,
        "--force-new",
        help="Treat all documents as NEW (skip diffing, run QA generation only)",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging (DEBUG level)"
    ),
) -> None:
    """Run a single poll cycle for testing.

    Useful for:
    - Testing GraphQL queries and authentication
    - Validating configuration
    - Manual polling without running the daemon
    - Initial bootstrap with --force-new

    With --force-new:
    - All documents are treated as NEW (no change detection)
    - Skips diff generation (no old/new comparison)
    - Only runs QA generation on current documents
    - Useful for initial bootstrap or re-processing entire corpus
    """
    configure_logging(verbose)

    try:
        from pathlib import Path

        from doc_diff_tracker.graphql.client import GraphQLClient
        from doc_diff_tracker.graphql.config import load_graphql_settings
        from doc_diff_tracker.graphql.fetcher import ContentFetcher
        from doc_diff_tracker.graphql.pipeline import PipelineRunner
        from doc_diff_tracker.graphql.scheduler import PollingScheduler
        from doc_diff_tracker.graphql.state import StateManager

        logger.info(
            "daemon_run_once_command",
            config=config,
            query_set=query_set,
            force_new=force_new,
        )

        typer.echo("Running single poll cycle...")
        typer.echo(f"Configuration: {config}")
        if query_set:
            typer.echo(f"Query set filter: {query_set}")
        if force_new:
            typer.echo(
                "Force new mode: treating all documents as NEW (no diff generation)"
            )

        # Load configuration
        config_path = Path(config)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config}")

        settings = load_graphql_settings(config_path)

        # Initialize components (same as daemon-start)
        # Use cert_path for SSL verification if provided, otherwise use verify boolean
        ssl_verify: bool | str = (
            settings.graphql.ssl.cert_path
            or settings.graphql_cert_path
            or settings.graphql.ssl.verify
        )

        client = GraphQLClient(
            endpoint=settings.graphql.endpoint,
            api_scope=settings.graphql.api_scope,
            client_id=settings.graphql_client_id,
            client_secret=settings.graphql_client_secret,
            token_url=settings.graphql_token_url,
            apollographql_client_name=settings.apollographql_client_name,
            apollographql_client_version=settings.graphql.apollographql_client_version,
            ssl_verify=ssl_verify,
            timeout=settings.graphql.polling.timeout_seconds,
            retry_attempts=settings.graphql.polling.retry_attempts,
        )

        download_dir = Path(settings.content.download_dir)
        fetcher = ContentFetcher(
            get_access_token=client.get_token_for_content_fetching(),
            download_dir=download_dir,
            max_size_mb=settings.content.max_file_size_mb,
            timeout=settings.content.timeout_seconds,
            max_workers=10,
            ssl_verify=ssl_verify,
        )

        state_file = Path(settings.state.file_path)
        state_manager = StateManager(
            state_file=state_file,
            backup_enabled=settings.state.backup_enabled,
            backup_count=settings.state.backup_count,
            prune_removed=settings.state.prune_removed_documents,
            cleanup_files=settings.state.cleanup_old_files,
        )

        pipeline_runner = PipelineRunner(state_manager)

        scheduler = PollingScheduler(
            settings=settings,
            client=client,
            fetcher=fetcher,
            state_manager=state_manager,
            pipeline_runner=pipeline_runner,
        )

        # Run single poll cycle
        typer.echo("\nStarting poll...")
        scheduler.run_once(query_set_filter=query_set, force_new=force_new)

        typer.echo("\n✓ Poll cycle complete")
        logger.info("daemon_run_once_completed")

    except FileNotFoundError as e:
        logger.error(
            "daemon_run_once_failed", error_type="file_not_found", error=str(e)
        )
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        logger.error(
            "daemon_run_once_failed", error_type=type(e).__name__, error=str(e)
        )
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    app()
