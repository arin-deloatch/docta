"""Pipeline runner for GraphQL polling service.

Orchestrates the complete diff + QA generation pipeline for polled documents.
Uses direct function imports (not subprocess) for better error handling.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from docta.output.reporting import (
    write_html_diff_report,
    write_report,
)
from docta.utils.cli_helpers import (
    execute_manifest_comparison,
    validate_common_inputs,
)
from docta.utils.scanner import scan_and_compare

if TYPE_CHECKING:
    from docta.graphql.models import QuerySetConfig
    from docta.graphql.state import StateManager

logger = structlog.get_logger(__name__)


class PipelineRunner:
    """Runs doc-diff and QA generation pipeline for modified documents."""

    def __init__(self, state_manager: StateManager):
        """Initialize pipeline runner.

        Args:
            state_manager: StateManager instance for tracking pipeline status
        """
        self.state_manager = state_manager
        self.logger = structlog.get_logger(__name__)

    def run_for_new_documents(
        self,
        query_set: QuerySetConfig,
        document_urls: list[str],
        workspace_base: Path,
    ) -> None:
        """Run QA generation for NEW documents (no diff, just QA from added docs).

        Args:
            query_set: Query set configuration
            document_urls: List of new document URLs
            workspace_base: Base path for temporary workspace

        Raises:
            RuntimeError: If pipeline execution fails
        """
        if not document_urls:
            self.logger.info("no_new_documents_to_process", query_set=query_set.name)
            return

        self.logger.info(
            "processing_new_documents",
            query_set=query_set.name,
            count=len(document_urls),
        )

        # Create workspace for this run
        timestamp = int(time.time())
        workspace = workspace_base / f"{query_set.name}_new_{timestamp}"
        new_dir = workspace / "new"
        new_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Copy new document versions to workspace
            copied_count = self.state_manager.copy_current_versions_to_workspace(query_set.name, document_urls, new_dir)

            if copied_count == 0:
                self.logger.warning(
                    "no_documents_copied_skipping_pipeline",
                    query_set=query_set.name,
                )
                return

            self.logger.info(
                "documents_copied_to_workspace",
                query_set=query_set.name,
                copied=copied_count,
                workspace=str(new_dir),
            )

            # Create output directory
            output_dir = Path(query_set.pipeline.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            # Create a minimal delta report for NEW documents
            # This is needed by the QA generation pipeline
            delta_report_path = output_dir / "delta_report_new.json"
            self._create_minimal_delta_report_for_new(new_dir, delta_report_path, query_set.pipeline.version_label)

            # Run QA generation for added documents only (if enabled)
            if query_set.pipeline.run_qa_generation:
                self.logger.info(
                    "running_qa_generation_for_new_documents",
                    query_set=query_set.name,
                )

                # Lazy import to avoid loading QA dependencies unless needed
                from qa_generation.config.settings import (
                    load_settings,
                )  # pylint: disable=import-outside-toplevel
                from qa_generation.pipeline.orchestrator import (  # pylint: disable=import-outside-toplevel
                    generate_qa_from_delta_report,
                )

                qa_settings = load_settings(yaml_path=query_set.pipeline.qa_config)
                qa_settings.setup_environment()

                qa_output_path = output_dir / "qa_pairs_new.json"

                qa_pairs = generate_qa_from_delta_report(
                    delta_report_path=delta_report_path,
                    output_path=qa_output_path,
                    settings=qa_settings,
                    output_format="json",
                    allow_overwrite=True,
                )

                self.logger.info(
                    "qa_generation_complete_for_new",
                    query_set=query_set.name,
                    qa_pairs=len(qa_pairs),
                    output=str(qa_output_path),
                )
            else:
                self.logger.info(
                    "qa_generation_disabled_for_new_documents",
                    query_set=query_set.name,
                )

            # Mark documents as processed
            self.state_manager.mark_documents_pipeline_completed(query_set.name, document_urls)

            self.logger.info(
                "new_documents_pipeline_complete",
                query_set=query_set.name,
                documents_processed=len(document_urls),
            )

        except Exception as e:
            self.logger.error(
                "new_documents_pipeline_failed",
                query_set=query_set.name,
                error=str(e),
                exc_info=True,
            )
            # DO NOT mark as processed - will retry on next poll
            raise RuntimeError(f"Pipeline failed for new documents in {query_set.name}: {e}") from e

        finally:
            # Cleanup workspace
            if workspace.exists():
                shutil.rmtree(workspace)
                self.logger.debug("workspace_cleaned", path=str(workspace))

    def run_for_modified_documents(  # pylint: disable=too-many-locals
        self,
        query_set: QuerySetConfig,
        document_urls: list[str],
        workspace_base: Path,
    ) -> None:
        """Run full diff + QA pipeline for MODIFIED documents.

        Args:
            query_set: Query set configuration
            document_urls: List of modified document URLs
            workspace_base: Base path for temporary workspace

        Raises:
            RuntimeError: If pipeline execution fails
        """
        if not document_urls:
            self.logger.info("no_modified_documents_to_process", query_set=query_set.name)
            return

        self.logger.info(
            "processing_modified_documents",
            query_set=query_set.name,
            count=len(document_urls),
        )

        # Create workspace for this run
        timestamp = int(time.time())
        workspace = workspace_base / f"{query_set.name}_modified_{timestamp}"
        old_dir = workspace / "old"
        new_dir = workspace / "new"
        old_dir.mkdir(parents=True, exist_ok=True)
        new_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Copy old and new versions to workspace
            copied_old = self.state_manager.copy_previous_versions_to_workspace(query_set.name, document_urls, old_dir)
            copied_new = self.state_manager.copy_current_versions_to_workspace(query_set.name, document_urls, new_dir)

            if copied_old == 0 or copied_new == 0:
                self.logger.warning(
                    "insufficient_versions_skipping_pipeline",
                    query_set=query_set.name,
                    copied_old=copied_old,
                    copied_new=copied_new,
                )
                return

            self.logger.info(
                "documents_copied_to_workspace",
                query_set=query_set.name,
                copied_old=copied_old,
                copied_new=copied_new,
                workspace=str(workspace),
            )

            # Create output directory
            output_dir = Path(query_set.pipeline.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            # Step 1: Run delta detection
            self.logger.info("running_delta_detection", query_set=query_set.name)

            old_root, new_root = validate_common_inputs(str(old_dir), str(new_dir), allow_symlinks=False)

            delta_report = execute_manifest_comparison(
                old_root_path=old_root,
                new_root_path=new_root,
                old_version="previous",
                new_version=query_set.pipeline.version_label,
                rename_threshold=85.0,
                allow_symlinks=False,
            )

            delta_report_path = output_dir / "delta_report.json"
            write_report(delta_report, str(delta_report_path))

            self.logger.info(
                "delta_detection_complete",
                query_set=query_set.name,
                output=str(delta_report_path),
                unchanged=len(delta_report.unchanged),
                modified=len(delta_report.modified),
                added=len(delta_report.added),
                removed=len(delta_report.removed),
            )

            # Step 2: Run semantic diff
            self.logger.info("running_semantic_diff", query_set=query_set.name)

            semantic_report = scan_and_compare(
                report_path=delta_report_path,
                old_root=old_root,
                new_root=new_root,
                include_modified=True,
                include_renamed=True,
                max_files=None,
            )

            semantic_report_path = output_dir / "semantic_diff_report.json"
            write_html_diff_report(semantic_report, str(semantic_report_path))

            self.logger.info(
                "semantic_diff_complete",
                query_set=query_set.name,
                output=str(semantic_report_path),
                num_results=len(semantic_report.results),
            )

            # Step 3: Run QA generation (if enabled)
            if query_set.pipeline.run_qa_generation:
                self.logger.info("running_qa_generation", query_set=query_set.name)

                # Lazy import to avoid loading QA dependencies unless needed
                from qa_generation.config.settings import (
                    load_settings,
                )  # pylint: disable=import-outside-toplevel
                from qa_generation.pipeline.orchestrator import (  # pylint: disable=import-outside-toplevel
                    generate_qa_from_both_sources,
                )

                qa_settings = load_settings(yaml_path=query_set.pipeline.qa_config)
                qa_settings.setup_environment()

                qa_output_path = output_dir / "qa_pairs.json"

                qa_pairs = generate_qa_from_both_sources(
                    delta_report_path=delta_report_path,
                    semantic_diff_report_path=semantic_report_path,
                    output_path=qa_output_path,
                    settings=qa_settings,
                    output_format="json",
                    allow_overwrite=True,
                )

                self.logger.info(
                    "qa_generation_complete",
                    query_set=query_set.name,
                    qa_pairs=len(qa_pairs),
                    output=str(qa_output_path),
                )
            else:
                self.logger.info("qa_generation_disabled", query_set=query_set.name)

            # Mark documents as processed
            self.state_manager.mark_documents_pipeline_completed(query_set.name, document_urls)

            self.logger.info(
                "modified_documents_pipeline_complete",
                query_set=query_set.name,
                documents_processed=len(document_urls),
            )

        except Exception as e:
            self.logger.error(
                "modified_documents_pipeline_failed",
                query_set=query_set.name,
                error=str(e),
                exc_info=True,
            )
            # DO NOT mark as processed - will retry on next poll
            raise RuntimeError(f"Pipeline failed for modified documents in {query_set.name}: {e}") from e

        finally:
            # Cleanup workspace
            if workspace.exists():
                shutil.rmtree(workspace)
                self.logger.debug("workspace_cleaned", path=str(workspace))

    def _create_minimal_delta_report_for_new(self, new_dir: Path, output_path: Path, version_label: str) -> None:
        """Create a minimal delta report for NEW documents.

        This creates a delta report where all documents are marked as "added"
        so they can be processed by the QA generation pipeline.

        Args:
            new_dir: Directory containing new documents
            output_path: Path to write delta report
            version_label: Version label for new documents
        """
        from docta.models.models import (
            DeltaReport,
            DocumentRecord,
        )  # pylint: disable=import-outside-toplevel

        # Scan new directory for HTML files
        added_docs = []
        for html_file in sorted(new_dir.glob("*.html")):
            # Extract topic slug from filename (if possible)
            topic_slug = html_file.stem

            added_doc = DocumentRecord(
                version=version_label,
                root=str(new_dir),
                relative_path=html_file.name,
                topic_slug=topic_slug,
                html_filename=html_file.name,
                raw_hash="",  # Not needed for added docs
            )
            added_docs.append(added_doc)

        # Create minimal delta report
        delta_report = DeltaReport(
            old_version="none",
            new_version=version_label,
            unchanged=[],
            modified=[],
            renamed_candidates=[],
            removed=[],
            added=added_docs,
        )

        # Write to file
        write_report(delta_report, str(output_path))

        self.logger.debug(
            "minimal_delta_report_created",
            output=str(output_path),
            added_count=len(added_docs),
        )
