"""Factory for creating GraphQL polling daemon components.

This module provides a single factory function to initialize all components
needed for the GraphQL polling daemon, eliminating duplication between
daemon commands.
"""

from __future__ import annotations

from pathlib import Path

import structlog

from docta.graphql.client import GraphQLClient
from docta.graphql.config import load_graphql_settings
from docta.graphql.fetcher import ContentFetcher
from docta.graphql.models import GraphQLPollingSettings
from docta.graphql.pipeline import PipelineRunner
from docta.graphql.scheduler import PollingScheduler
from docta.graphql.state import StateManager

logger = structlog.get_logger(__name__)


def create_polling_components(
    config_path: Path,
) -> tuple[
    GraphQLPollingSettings,
    GraphQLClient,
    ContentFetcher,
    StateManager,
    PipelineRunner,
    PollingScheduler,
]:
    """Initialize all GraphQL polling components from configuration.

    This factory function loads configuration and creates all the components
    needed to run the GraphQL polling daemon. It handles:
    - Loading and validating configuration
    - Determining SSL verification strategy
    - Creating OAuth-authenticated GraphQL client
    - Setting up content fetcher with token callback
    - Initializing state management with backup/cleanup
    - Creating pipeline runner
    - Assembling the polling scheduler

    Args:
        config_path: Path to GraphQL polling YAML configuration file

    Returns:
        Tuple of (settings, client, fetcher, state_manager, pipeline_runner, scheduler)

    Raises:
        FileNotFoundError: If configuration file doesn't exist
        ValueError: If configuration is invalid
        ValidationError: If settings fail validation

    Example:
        >>> config_path = Path("config/graphql_polling.yaml")
        >>> settings, client, fetcher, state, pipeline, scheduler = (
        ...     create_polling_components(config_path)
        ... )
        >>> scheduler.run_forever()
    """
    logger.info("loading_graphql_configuration", config=str(config_path))

    # Validate config file exists
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    # Load configuration
    settings = load_graphql_settings(config_path)

    logger.info(
        "configuration_loaded",
        query_sets=len(settings.graphql.query_sets),
        polling_interval=settings.graphql.polling.interval_minutes,
    )

    # Initialize GraphQL client
    logger.info("initializing_graphql_client")

    # Use cert_path for SSL verification if provided, otherwise use verify boolean
    ssl_verify: bool | str = settings.graphql.ssl.cert_path or settings.graphql_cert_path or settings.graphql.ssl.verify

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

    # Initialize content fetcher
    logger.info("initializing_content_fetcher")
    download_dir = Path(settings.content.download_dir)  # pylint: disable=no-member
    fetcher = ContentFetcher(
        get_access_token=client.get_token_for_content_fetching(),
        download_dir=download_dir,
        max_size_mb=settings.content.max_file_size_mb,  # pylint: disable=no-member
        timeout=settings.content.timeout_seconds,  # pylint: disable=no-member
        max_workers=10,  # Default, can be overridden per query set
        ssl_verify=ssl_verify,
    )

    # Initialize state manager
    logger.info("initializing_state_manager")
    state_file = Path(settings.state.file_path)  # pylint: disable=no-member
    state_manager = StateManager(
        state_file=state_file,
        backup_enabled=settings.state.backup_enabled,  # pylint: disable=no-member
        backup_count=settings.state.backup_count,  # pylint: disable=no-member
        prune_removed=settings.state.prune_removed_documents,  # pylint: disable=no-member
        cleanup_files=settings.state.cleanup_old_files,  # pylint: disable=no-member
    )

    # Initialize pipeline runner
    logger.info("initializing_pipeline_runner")
    pipeline_runner = PipelineRunner(state_manager)

    # Initialize scheduler
    logger.info("initializing_scheduler")
    scheduler = PollingScheduler(
        settings=settings,
        client=client,
        fetcher=fetcher,
        state_manager=state_manager,
        pipeline_runner=pipeline_runner,
    )

    logger.info("polling_components_initialized")

    return settings, client, fetcher, state_manager, pipeline_runner, scheduler
