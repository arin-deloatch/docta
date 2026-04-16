"""Synchronous polling scheduler for GraphQL document monitoring.

Orchestrates the polling loop with:
- Configurable intervals (default 60 minutes)
- Graceful shutdown handling (SIGTERM, SIGINT)
- Per-query-set execution with error isolation
- Change detection and pipeline triggering
"""

# pylint: disable=duplicate-code  # Similar error handling patterns to pipeline.py are intentional

from __future__ import annotations

import signal
import time
from datetime import UTC, datetime
from pathlib import Path

import structlog

from docta.graphql.client import GraphQLClient
from docta.graphql.fetcher import ContentFetcher
from docta.graphql.models import GraphQLPollingSettings
from docta.graphql.pipeline import PipelineRunner
from docta.graphql.state import StateManager


class PollingScheduler:
    """Orchestrates synchronous polling loop for GraphQL document monitoring."""

    def __init__(  # pylint: disable=too-many-positional-arguments
        self,
        settings: GraphQLPollingSettings,
        client: GraphQLClient,
        fetcher: ContentFetcher,
        state_manager: StateManager,
        pipeline_runner: PipelineRunner,
    ):
        """Initialize polling scheduler.

        Args:
            settings: Complete GraphQL polling settings
            client: GraphQL client for API queries
            fetcher: Content fetcher for downloading HTML
            state_manager: State manager for persistence
            pipeline_runner: Pipeline runner for diff + QA generation
        """
        self.settings = settings
        self.client = client
        self.fetcher = fetcher
        self.state_manager = state_manager
        self.pipeline_runner = pipeline_runner
        self.logger = structlog.get_logger(__name__)
        self._shutdown_requested = False

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum: int, frame) -> None:  # type: ignore[no-untyped-def]  # pylint: disable=unused-argument
        """Handle shutdown signals (SIGTERM, SIGINT).

        Args:
            signum: Signal number
            frame: Current stack frame (required by signal handler signature, unused)
        """
        sig_name = signal.Signals(signum).name
        self.logger.info("shutdown_signal_received", signal=sig_name, signum=signum)
        self._shutdown_requested = True

    def run_forever(self) -> None:
        """Run polling loop indefinitely until shutdown signal received."""
        interval_minutes = self.settings.graphql.polling.interval_minutes
        initial_delay = self.settings.graphql.polling.initial_delay_seconds

        self.logger.info(
            "polling_started",
            interval_minutes=interval_minutes,
            initial_delay_seconds=initial_delay,
            query_sets=len(self.settings.graphql.query_sets),
        )

        # Initial delay before first poll
        if initial_delay > 0:
            self.logger.info("initial_delay_sleeping", seconds=initial_delay)
            self._sleep_with_shutdown_check(initial_delay)

        # Main polling loop
        while not self._shutdown_requested:
            cycle_start = time.time()

            try:
                self.poll_all_query_sets()

                cycle_duration = time.time() - cycle_start
                self.logger.info(
                    "poll_cycle_complete",
                    duration_seconds=round(cycle_duration, 2),
                    next_poll_in_minutes=interval_minutes,
                )

                # Sleep until next interval
                sleep_seconds = interval_minutes * 60
                self._sleep_with_shutdown_check(sleep_seconds)

            except Exception as e:  # pylint: disable=broad-exception-caught  # Main polling loop must handle all errors
                self.logger.error(
                    "poll_cycle_failed",
                    error=str(e),
                    exc_info=True,
                )
                # Wait before retrying to avoid tight error loops
                self.logger.info("waiting_before_retry", seconds=60)
                self._sleep_with_shutdown_check(60)

        self.logger.info("polling_stopped_gracefully")

    def run_once(self, query_set_filter: str | None = None, force_new: bool = False) -> None:
        """Run a single poll cycle (for testing/debugging).

        Args:
            query_set_filter: Optional name of specific query set to poll
            force_new: If True, treat all documents as NEW (clear state before processing)
        """
        self.logger.info(
            "running_single_poll_cycle",
            query_set_filter=query_set_filter,
            force_new=force_new,
        )

        if force_new:
            self.logger.warning("force_new_enabled_clearing_state")
            # If force_new, we'll clear the state for the specified query set
            # This makes all documents appear as NEW

        self.poll_all_query_sets(query_set_filter=query_set_filter, force_new=force_new)
        self.logger.info("single_poll_cycle_complete")

    def poll_all_query_sets(self, query_set_filter: str | None = None, force_new: bool = False) -> None:
        """Poll all enabled query sets.

        Args:
            query_set_filter: Optional name of specific query set to poll
            force_new: If True, treat all documents as NEW (skip change detection)
        """
        for query_set in self.settings.graphql.query_sets:
            if not query_set.enabled:
                self.logger.debug("query_set_disabled_skipping", name=query_set.name)
                continue

            if query_set_filter and query_set.name != query_set_filter:
                self.logger.debug(
                    "query_set_filtered_skipping",
                    name=query_set.name,
                    filter=query_set_filter,
                )
                continue

            try:
                self.poll_query_set(query_set, force_new=force_new)
            except Exception as e:  # pylint: disable=broad-exception-caught  # Continue with other query sets despite errors
                self.logger.error(
                    "query_set_poll_failed",
                    query_set=query_set.name,
                    error=str(e),
                    exc_info=True,
                )
                # Continue with other query sets instead of failing completely

    def poll_query_set(  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        self, query_set, force_new: bool = False  # type: ignore[no-untyped-def]
    ) -> None:
        """Poll a single query set and process changes.

        Args:
            query_set: Query set configuration
            force_new: If True, treat all documents as NEW (skip change detection)
        """
        self.logger.info("poll_started", query_set=query_set.name, force_new=force_new)
        poll_start = time.time()

        # Load current state
        state = self.state_manager.load_state()

        # Execute GraphQL query
        self.logger.debug(
            "executing_graphql_query",
            query_set=query_set.name,
            endpoint=str(self.settings.graphql.endpoint),
        )

        response = self.client.execute_query(query_set.query, query_set.variables)
        fetched_nodes = self.client.parse_documentation_titles(response)

        self.logger.info(
            "graphql_query_executed",
            query_set=query_set.name,
            documents_returned=len(fetched_nodes),
        )

        if not fetched_nodes:
            self.logger.warning("no_documents_returned_from_graphql", query_set=query_set.name)
            return

        # Handle force_new mode
        if force_new:
            self.logger.info(
                "force_new_mode_treating_all_as_new",
                query_set=query_set.name,
                count=len(fetched_nodes),
            )
            new_docs = fetched_nodes
            modified_docs: list = []
        else:
            # Detect changes
            new_docs, modified_docs = self.state_manager.detect_changes(query_set.name, fetched_nodes, state)

        # Prune documents no longer in GraphQL
        current_urls = {str(node.singlePage.contentUrl) for node in fetched_nodes if node.singlePage}
        pruned_count = self.state_manager.prune_removed_documents(query_set.name, current_urls, state)

        if pruned_count > 0:
            self.logger.info("documents_pruned", count=pruned_count)

        total_to_process = len(new_docs) + len(modified_docs)

        if total_to_process == 0:
            self.logger.info(
                "no_changes_detected",
                query_set=query_set.name,
                total_documents=len(fetched_nodes),
            )
            # Update last poll timestamp
            if query_set.name in state.query_sets:
                state.query_sets[query_set.name].last_poll = datetime.now(UTC)
                state.query_sets[query_set.name].last_success = datetime.now(UTC)
                self.state_manager.save_state(state)
            return

        self.logger.info(
            "changes_detected",
            query_set=query_set.name,
            new=len(new_docs),
            modified=len(modified_docs),
            total_to_process=total_to_process,
        )

        # Fetch content for changed documents
        documents_to_fetch = new_docs + modified_docs
        self.logger.info(
            "fetching_documents",
            query_set=query_set.name,
            count=len(documents_to_fetch),
            max_concurrent=query_set.pipeline.max_concurrent_fetches,
        )

        fetch_results = self.fetcher.fetch_multiple(
            documents_to_fetch,
            query_set.name,
        )

        self.logger.info(
            "documents_fetched",
            query_set=query_set.name,
            successful=len(fetch_results),
            failed=len(documents_to_fetch) - len(fetch_results),
        )

        # Update state with fetched documents
        for node in documents_to_fetch:
            if not node.singlePage:
                continue

            url = str(node.singlePage.contentUrl)
            if url not in fetch_results:
                self.logger.warning("document_fetch_failed_skipping", url=url)
                continue

            # fetch_results maps URL -> DocumentVersion
            new_version = fetch_results[url]

            self.state_manager.update_document(query_set.name, url, new_version, state)

        # Save state before running pipeline
        self.state_manager.save_state(state)

        # Process NEW documents (no diff, just QA generation)
        if new_docs:
            new_urls = [str(node.singlePage.contentUrl) for node in new_docs if node.singlePage and str(node.singlePage.contentUrl) in fetch_results]

            if new_urls:
                workspace_base = Path("tmp/graphql_polling")
                workspace_base.mkdir(parents=True, exist_ok=True)

                self.logger.info(
                    "processing_new_documents_pipeline",
                    query_set=query_set.name,
                    count=len(new_urls),
                )

                try:
                    self.pipeline_runner.run_for_new_documents(query_set, new_urls, workspace_base)
                except Exception as e:  # pylint: disable=broad-exception-caught  # Daemon must continue despite pipeline errors
                    self.logger.error(
                        "new_documents_pipeline_failed",
                        query_set=query_set.name,
                        error=str(e),
                        exc_info=True,
                    )

        # Process MODIFIED documents (full diff + QA pipeline)
        if modified_docs:
            modified_urls = [str(node.singlePage.contentUrl) for node in modified_docs if node.singlePage and str(node.singlePage.contentUrl) in fetch_results]

            if modified_urls:
                workspace_base = Path("tmp/graphql_polling")
                workspace_base.mkdir(parents=True, exist_ok=True)

                self.logger.info(
                    "processing_modified_documents_pipeline",
                    query_set=query_set.name,
                    count=len(modified_urls),
                )

                try:
                    self.pipeline_runner.run_for_modified_documents(query_set, modified_urls, workspace_base)
                except Exception as e:  # pylint: disable=broad-exception-caught  # Daemon must continue despite pipeline errors
                    self.logger.error(
                        "modified_documents_pipeline_failed",
                        query_set=query_set.name,
                        error=str(e),
                        exc_info=True,
                    )

        # Update statistics
        query_state = state.query_sets.get(query_set.name)
        if query_state:
            query_state.last_poll = datetime.now(UTC)
            query_state.last_success = datetime.now(UTC)
            query_state.stats.total_polls += 1
            query_state.stats.documents_with_changes += total_to_process
            self.state_manager.save_state(state)

        poll_duration = time.time() - poll_start
        self.logger.info(
            "poll_complete",
            query_set=query_set.name,
            duration_seconds=round(poll_duration, 2),
        )

    def _sleep_with_shutdown_check(self, seconds: int) -> None:
        """Sleep for specified seconds with periodic shutdown checks.

        Splits sleep into 1-second intervals to allow responsive shutdown.

        Args:
            seconds: Total seconds to sleep
        """
        for _ in range(seconds):
            if self._shutdown_requested:
                break
            time.sleep(1)
