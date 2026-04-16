"""GraphQL polling daemon management commands."""

# pylint: disable=duplicate-code

from __future__ import annotations

import sys
from pathlib import Path

import structlog
import typer

from docta.cli._error_handling import handle_cli_errors
from docta.utils.logging import configure_logging

logger = structlog.get_logger(__name__)
app = typer.Typer(help="GraphQL polling daemon management")


@app.command()
@handle_cli_errors
def start(
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
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging (DEBUG level)"),
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

    # Lazy import to avoid loading GraphQL dependencies unless needed
    from docta.graphql.factory import (  # pylint: disable=import-outside-toplevel
        create_polling_components,
    )

    logger.info("daemon_start_command", config=config, foreground=foreground)
    typer.echo("Starting GraphQL polling daemon...")
    typer.echo(f"Configuration: {config}")

    # Initialize all components from configuration
    config_path = Path(config)
    settings, _client, _fetcher, _state_manager, _pipeline_runner, scheduler = create_polling_components(config_path)

    typer.echo(f"Loaded {len(settings.graphql.query_sets)} query set(s), " f"polling interval: {settings.graphql.polling.interval_minutes} minutes")

    # Run scheduler
    if foreground:
        typer.echo("Running in foreground (Ctrl+C to stop)...")
        logger.info("starting_foreground_polling")
        scheduler.run_forever()
    else:
        # For background mode, we'd typically use a process manager like systemd
        # For now, just run in foreground and advise user to use systemd/Docker
        typer.echo("Background daemonization not implemented - use systemd or Docker")
        typer.echo("Running in foreground mode instead (Ctrl+C to stop)...")
        logger.info("starting_foreground_polling_fallback")
        scheduler.run_forever()

    logger.info("daemon_stopped")


@app.command()
def stop() -> None:
    """Stop the running GraphQL polling daemon.

    This command is a placeholder for future implementation.
    Currently, use Ctrl+C to stop a foreground daemon, or
    `systemctl stop docta-graphql-poller` for systemd service.
    """
    typer.echo("Daemon stop not implemented - use:")
    typer.echo("  - Ctrl+C for foreground daemon")
    typer.echo("  - systemctl stop docta-graphql-poller for systemd")
    typer.echo("  - docker-compose down for Docker")


@app.command()
@handle_cli_errors
def status(
    *,
    config: str = typer.Option(
        "config/graphql_polling.yaml",
        help="Path to GraphQL polling configuration",
    ),
) -> None:
    """Check status of GraphQL polling daemon.

    Reads the state file and displays polling statistics.
    """
    # Lazy imports to avoid loading GraphQL dependencies unless needed
    from docta.graphql.config import (  # pylint: disable=import-outside-toplevel
        load_graphql_settings,
    )
    from docta.graphql.state import (  # pylint: disable=import-outside-toplevel
        StateManager,
    )

    # Load configuration to get state file path
    config_path = Path(config)
    if not config_path.exists():
        typer.echo(f"Configuration file not found: {config}", err=True)
        sys.exit(1)

    settings = load_graphql_settings(config_path)
    state_file = Path(settings.state.file_path)  # pylint: disable=no-member

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

    for query_set_name, query_state in state.query_sets.items():  # pylint: disable=no-member
        typer.echo(f"Query Set: {query_set_name}")
        typer.echo(f"  Last poll: {query_state.last_poll or 'Never'}")
        typer.echo(f"  Last success: {query_state.last_success or 'Never'}")
        typer.echo(f"  Total documents: {query_state.stats.total_documents}")
        typer.echo(f"  Total polls: {query_state.stats.total_polls}")
        typer.echo(f"  Documents with changes: {query_state.stats.documents_with_changes}")
        typer.echo(f"  Total pipeline runs: {query_state.stats.total_pipeline_runs}")
        typer.echo()


@app.command(name="run-once")
@handle_cli_errors
def run_once(
    *,
    config: str = typer.Option(..., help="Path to GraphQL polling configuration"),
    query_set: str | None = typer.Option(None, "--query-set", help="Optional: specific query set to poll"),
    force_new: bool = typer.Option(
        False,
        "--force-new",
        help="Treat all documents as NEW (skip diffing, run QA generation only)",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging (DEBUG level)"),
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

    # Lazy import to avoid loading GraphQL dependencies unless needed
    from docta.graphql.factory import (  # pylint: disable=import-outside-toplevel
        create_polling_components,
    )

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
        typer.echo("Force new mode: treating all documents as NEW (no diff generation)")

    # Initialize all components from configuration
    config_path = Path(config)
    _settings, _client, _fetcher, _state_manager, _pipeline_runner, scheduler = create_polling_components(config_path)

    # Run single poll cycle
    typer.echo("\nStarting poll...")
    scheduler.run_once(query_set_filter=query_set, force_new=force_new)

    typer.echo("\n✓ Poll cycle complete")
    logger.info("daemon_run_once_completed")
