"""State persistence manager for GraphQL polling service."""

from __future__ import annotations

import fcntl
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import structlog
from pydantic import HttpUrl

from docta.graphql.models import (
    DocumentState,
    DocumentVersion,
    DocumentationTitleNode,
    PollingState,
    QuerySetState,
)


class StateManager:
    """Manages polling state persistence with file locking and backups."""

    def __init__(
        self,
        state_file: Path,
        *,
        backup_enabled: bool = True,
        backup_count: int = 5,
        prune_removed: bool = True,
        cleanup_files: bool = True,
    ):
        """Initialize state manager.

        Args:
            state_file: Path to state JSON file
            backup_enabled: Enable automatic backups
            backup_count: Number of backup files to retain
            prune_removed: Remove documents no longer in GraphQL
            cleanup_files: Delete HTML files for pruned/rotated documents
        """
        self.state_file = state_file
        self.backup_enabled = backup_enabled
        self.backup_count = backup_count
        self.prune_removed = prune_removed
        self.cleanup_files = cleanup_files
        self.logger = structlog.get_logger(__name__)

    def load_state(self) -> PollingState:
        """Load state from JSON file with file locking.

        Returns:
            PollingState object

        Creates new state if file doesn't exist.
        Attempts to load from backup if primary file is corrupted.
        """
        # Create parent directory if needed
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # If file doesn't exist, return new state
        if not self.state_file.exists():
            self.logger.info("state_file_not_found", creating_new=True)
            return PollingState()

        # Try to load primary state file
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                # Acquire shared lock for reading
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                    state = PollingState(**data)
                    self.logger.info(
                        "state_loaded",
                        query_sets=len(state.query_sets),
                    )
                    return state
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        except (json.JSONDecodeError, ValueError) as e:
            self.logger.warning(
                "state_file_corrupted",
                error=str(e),
                attempting_backup_load=True,
            )

            # Try to load from backups
            for i in range(1, self.backup_count + 1):
                backup_path = Path(f"{self.state_file}.{i}")
                if backup_path.exists():
                    try:
                        with open(backup_path, encoding="utf-8") as f:
                            data = json.load(f)
                            state = PollingState(**data)
                            self.logger.info(
                                "state_loaded_from_backup",
                                backup_number=i,
                            )
                            return state
                    except (json.JSONDecodeError, ValueError):
                        continue

            # All backups failed, create new state
            self.logger.error("all_backups_failed", creating_new_state=True)
            return PollingState()

    def save_state(self, state: PollingState) -> None:
        """Save state to JSON file with atomic write and backup.

        Args:
            state: PollingState to save

        Uses atomic write (temp file + rename) to prevent corruption.
        Creates backup of previous state if enabled.
        """
        # Update timestamp
        state.last_updated = datetime.now(UTC)

        # Create parent directory if needed
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Create backup if enabled and file exists
        if self.backup_enabled and self.state_file.exists():
            self._rotate_backups()

        # Atomic write: write to temp file, then rename
        temp_file = self.state_file.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                # Acquire exclusive lock for writing
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(
                        state.model_dump(mode="json"),
                        f,
                        indent=2,
                        default=str,
                    )
                    f.flush()
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            # Atomic rename
            temp_file.rename(self.state_file)

            self.logger.info("state_saved", path=str(self.state_file))

        except Exception as e:
            # Clean up temp file on error
            if temp_file.exists():
                temp_file.unlink()
            self.logger.error("state_save_failed", error=str(e))
            raise

    def _rotate_backups(self) -> None:
        """Rotate backup files (state.json.1, state.json.2, ...)."""
        # Remove oldest backup if at limit
        oldest = Path(f"{self.state_file}.{self.backup_count}")
        if oldest.exists():
            oldest.unlink()

        # Rotate existing backups
        for i in range(self.backup_count - 1, 0, -1):
            old_backup = Path(f"{self.state_file}.{i}")
            new_backup = Path(f"{self.state_file}.{i + 1}")
            if old_backup.exists():
                old_backup.rename(new_backup)

        # Create new backup from current state
        if self.state_file.exists():
            backup_path = Path(f"{self.state_file}.1")
            shutil.copy2(self.state_file, backup_path)

    def detect_changes(
        self,
        query_set_name: str,
        fetched_nodes: list[DocumentationTitleNode],
        current_state: PollingState,
    ) -> tuple[list[DocumentationTitleNode], list[DocumentationTitleNode]]:
        """Detect NEW and MODIFIED documents.

        Compares GraphQL modified timestamps with state file timestamps.
        Loop prevention: After processing, state is updated with latest timestamp,
        so next poll will find no changes unless document is modified again.

        Args:
            query_set_name: Name of query set
            fetched_nodes: Nodes from GraphQL query
            current_state: Current polling state

        Returns:
            (new_documents, modified_documents)
        """
        new_docs = []
        modified_docs = []
        unchanged_count = 0

        query_state = current_state.query_sets.get(query_set_name)
        if not query_state:
            # First poll - all documents are new
            self.logger.info(
                "first_poll_detected",
                query_set=query_set_name,
                total_documents=len(fetched_nodes),
            )
            return fetched_nodes, []

        for node in fetched_nodes:
            if not node.singlePage:
                continue

            url = str(node.singlePage.contentUrl)
            doc_state = query_state.documents.get(url)

            if not doc_state or not doc_state.current_version:
                # Never seen before - NEW
                new_docs.append(node)
                self.logger.debug(
                    "document_new",
                    url=url,
                    modified=node.singlePage.modified,
                )
            elif node.singlePage.modified > doc_state.current_version.modified:
                # GraphQL timestamp is NEWER than state - MODIFIED
                modified_docs.append(node)
                self.logger.debug(
                    "document_modified",
                    url=url,
                    old_modified=doc_state.current_version.modified,
                    new_modified=node.singlePage.modified,
                )
            else:
                # Timestamps match (or GraphQL is older) - UNCHANGED
                unchanged_count += 1
                self.logger.debug(
                    "document_unchanged",
                    url=url,
                    modified=node.singlePage.modified,
                )

        self.logger.info(
            "change_detection_complete",
            query_set=query_set_name,
            new=len(new_docs),
            modified=len(modified_docs),
            unchanged=unchanged_count,
            total=len(fetched_nodes),
        )

        return new_docs, modified_docs

    def update_document(
        self,
        query_set_name: str,
        url: str,
        new_fetch: DocumentVersion,
        state: PollingState,
    ) -> None:
        """Update document state with new fetch (rotate versions + cleanup).

        Rotation: current → previous, new → current
        Cleanup: Delete old previous_version HTML file (keep only 2 versions max)

        Args:
            query_set_name: Name of query set
            url: Document content URL
            new_fetch: Newly fetched document version
            state: Polling state to update
        """
        query_state = state.query_sets.setdefault(
            query_set_name,
            QuerySetState(),
        )

        doc_state = query_state.documents.get(url)
        if not doc_state:
            # First time seeing this document
            doc_state = DocumentState(
                content_url=HttpUrl(url),
                current_version=new_fetch,
                previous_version=None,
            )
        else:
            # Delete old previous_version HTML file (keep only 2 versions max)
            if self.cleanup_files and doc_state.previous_version and doc_state.previous_version.local_path:
                old_file = Path(doc_state.previous_version.local_path)
                if old_file.exists():
                    old_file.unlink()
                    self.logger.info(
                        "old_html_deleted",
                        path=str(old_file),
                        reason="version_rotation",
                    )

            # Rotate: current → previous, new → current
            doc_state.previous_version = doc_state.current_version
            doc_state.current_version = new_fetch

        query_state.documents[url] = doc_state

    def prune_removed_documents(
        self,
        query_set_name: str,
        current_graphql_urls: set[str],
        state: PollingState,
    ) -> int:
        """Remove documents from state that are no longer in GraphQL.

        Args:
            query_set_name: Name of query set
            current_graphql_urls: URLs returned by current GraphQL query
            state: Polling state to update

        Returns:
            Number of documents pruned
        """
        if not self.prune_removed:
            return 0

        query_state = state.query_sets.get(query_set_name)
        if not query_state:
            return 0

        # Find documents in state but not in GraphQL
        state_urls = set(query_state.documents.keys())
        removed_urls = state_urls - current_graphql_urls

        # Prune removed documents
        for url in removed_urls:
            doc_state = query_state.documents[url]

            # Clean up old HTML files if enabled
            if self.cleanup_files:
                if doc_state.current_version and doc_state.current_version.local_path:
                    Path(doc_state.current_version.local_path).unlink(missing_ok=True)
                if doc_state.previous_version and doc_state.previous_version.local_path:
                    Path(doc_state.previous_version.local_path).unlink(missing_ok=True)

            # Remove from state
            del query_state.documents[url]

            self.logger.info(
                "document_pruned",
                query_set=query_set_name,
                url=url,
                reason="not_in_graphql",
            )

        return len(removed_urls)

    def mark_pipeline_status(
        self,
        query_set_name: str,
        url: str,
        status: str,
        state: PollingState,
    ) -> None:
        """Mark pipeline status for a document.

        Args:
            query_set_name: Name of query set
            url: Document content URL
            status: Pipeline status (pending, running, completed, failed)
            state: Polling state to update
        """
        query_state = state.query_sets.get(query_set_name)
        if not query_state:
            return

        doc_state = query_state.documents.get(url)
        if doc_state:
            doc_state.pipeline_status = status
            doc_state.pipeline_last_run = datetime.now(UTC)

    def mark_documents_pipeline_completed(
        self,
        query_set_name: str,
        urls: list[str],
    ) -> None:
        """Mark multiple documents as pipeline completed.

        Args:
            query_set_name: Name of query set
            urls: List of document URLs to mark as completed
        """
        # Load current state
        state = self.load_state()

        # Mark each document as completed
        for url in urls:
            self.mark_pipeline_status(query_set_name, url, "completed", state)

        # Update stats
        query_state = state.query_sets.get(query_set_name)
        if query_state:
            query_state.stats.total_pipeline_runs += 1

        # Save state
        self.save_state(state)

        self.logger.info(
            "documents_marked_completed",
            query_set=query_set_name,
            count=len(urls),
        )

    def copy_current_versions_to_workspace(
        self,
        query_set_name: str,
        urls: list[str],
        target_dir: Path,
    ) -> int:
        """Copy current versions of documents to workspace directory.

        Args:
            query_set_name: Name of query set
            urls: List of document URLs to copy
            target_dir: Target directory for copying

        Returns:
            Number of files successfully copied
        """
        state = self.load_state()
        query_state = state.query_sets.get(query_set_name)
        if not query_state:
            return 0

        copied = 0
        for url in urls:
            doc_state = query_state.documents.get(url)
            if not doc_state or not doc_state.current_version:
                self.logger.warning(
                    "document_missing_current_version",
                    url=url,
                    query_set=query_set_name,
                )
                continue

            source_path = Path(doc_state.current_version.local_path)
            if not source_path.exists():
                self.logger.warning(
                    "current_version_file_missing",
                    url=url,
                    path=str(source_path),
                )
                continue

            # Use the same filename in workspace
            target_path = target_dir / source_path.name
            shutil.copy2(source_path, target_path)
            copied += 1

            self.logger.debug(
                "current_version_copied",
                url=url,
                source=str(source_path),
                target=str(target_path),
            )

        return copied

    def copy_previous_versions_to_workspace(
        self,
        query_set_name: str,
        urls: list[str],
        target_dir: Path,
    ) -> int:
        """Copy previous versions of documents to workspace directory.

        Args:
            query_set_name: Name of query set
            urls: List of document URLs to copy
            target_dir: Target directory for copying

        Returns:
            Number of files successfully copied
        """
        state = self.load_state()
        query_state = state.query_sets.get(query_set_name)
        if not query_state:
            return 0

        copied = 0
        for url in urls:
            doc_state = query_state.documents.get(url)
            if not doc_state or not doc_state.previous_version:
                self.logger.warning(
                    "document_missing_previous_version",
                    url=url,
                    query_set=query_set_name,
                )
                continue

            source_path = Path(doc_state.previous_version.local_path)
            if not source_path.exists():
                self.logger.warning(
                    "previous_version_file_missing",
                    url=url,
                    path=str(source_path),
                )
                continue

            # Use the same filename in workspace
            target_path = target_dir / source_path.name
            shutil.copy2(source_path, target_path)
            copied += 1

            self.logger.debug(
                "previous_version_copied",
                url=url,
                source=str(source_path),
                target=str(target_path),
            )

        return copied
