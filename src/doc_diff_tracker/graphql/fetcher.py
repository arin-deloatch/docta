"""Content fetcher for downloading HTML from GraphQL contentUrl."""

from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

import requests
import structlog
from pydantic import HttpUrl

from doc_diff_tracker.graphql.models import DocumentationTitleNode, DocumentVersion


class ContentFetcher:
    """Fetches HTML content with parallel downloading support."""

    def __init__(
        self,
        get_access_token: Callable[[], str],
        download_dir: Path,
        max_size_mb: int = 100,
        timeout: int = 60,
        max_workers: int = 10,
        ssl_verify: bool | str = True,
    ):
        """Initialize content fetcher.

        Args:
            get_access_token: Callable that returns current OAuth access token
            download_dir: Directory to store downloaded HTML files
            max_size_mb: Maximum file size in MB
            timeout: Request timeout in seconds
            max_workers: Maximum parallel downloads
            ssl_verify: SSL verification (bool or path to CA bundle)
        """
        self.get_access_token = get_access_token
        self.download_dir = download_dir
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.timeout = timeout
        self.max_workers = max_workers
        self.ssl_verify = ssl_verify
        self.logger = structlog.get_logger(__name__)

        # Create download directory
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def fetch_multiple(
        self,
        documents: list[DocumentationTitleNode],
        query_set_name: str,
    ) -> dict[str, DocumentVersion]:
        """Fetch multiple documents in parallel using ThreadPoolExecutor.

        Args:
            documents: List of documents to fetch
            query_set_name: Query set name for directory organization

        Returns:
            Dict mapping content URL to DocumentVersion
        """
        results = {}

        # Filter documents that have singlePage
        docs_to_fetch = [doc for doc in documents if doc.singlePage]

        if not docs_to_fetch:
            self.logger.info("no_documents_to_fetch")
            return results

        self.logger.info(
            "fetching_documents",
            count=len(docs_to_fetch),
            max_concurrent=self.max_workers,
        )

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all fetch tasks
            future_to_doc = {
                executor.submit(
                    self.fetch_single,
                    doc.singlePage.contentUrl,  # type: ignore[union-attr]
                    query_set_name,
                    doc.name,
                    doc.singlePage.modified,  # type: ignore[union-attr]
                ): doc
                for doc in docs_to_fetch
                if doc.singlePage  # Already filtered above
            }

            # Process completed tasks
            completed = 0
            failed = 0

            for future in as_completed(future_to_doc):
                doc = future_to_doc[future]
                try:
                    doc_version = future.result()
                    # Already filtered to docs with singlePage
                    url = str(doc.singlePage.contentUrl)  # type: ignore[union-attr]
                    results[url] = doc_version

                    completed += 1
                    self.logger.info(
                        "document_fetched",
                        document=doc.name,
                        progress=f"{completed}/{len(docs_to_fetch)}",
                        hash=doc_version.content_hash[:16],
                    )

                except Exception as e:
                    failed += 1
                    doc_name = doc.name if doc else "unknown"
                    self.logger.error(
                        "document_fetch_failed",
                        document=doc_name,
                        error=str(e),
                        progress=f"{completed + failed}/{len(docs_to_fetch)}",
                    )

        self.logger.info(
            "fetch_complete",
            total=len(docs_to_fetch),
            successful=completed,
            failed=failed,
        )

        return results

    def fetch_single(
        self,
        content_url: HttpUrl,
        query_set_name: str,
        document_name: str,
        modified: datetime,
    ) -> DocumentVersion:
        """Fetch a single HTML document with OAuth authentication.

        Args:
            content_url: URL to fetch HTML from
            query_set_name: Query set name for directory organization
            document_name: Document name for filename
            modified: Document modification timestamp

        Returns:
            DocumentVersion with fetched content info

        Raises:
            requests.HTTPError: If fetch fails
            ValueError: If content exceeds size limit
        """
        # Get fresh access token for this request
        access_token = self.get_access_token()

        # Fetch content with streaming to check size
        response = requests.get(
            str(content_url),
            headers={"Authorization": f"Bearer {access_token}"},
            verify=self.ssl_verify,
            timeout=self.timeout,
            stream=True,
        )
        response.raise_for_status()

        # Read content with size limit
        content = b""
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > self.max_size_bytes:
                raise ValueError(
                    f"Content exceeds {self.max_size_bytes} bytes "
                    f"(max {self.max_size_bytes // (1024 * 1024)}MB)"
                )

        # Compute content hash
        content_hash = hashlib.sha256(content).hexdigest()

        # Build local path with timestamp
        timestamp = modified.strftime("%Y%m%d")
        safe_name = "".join(
            c if c.isalnum() or c in "-_" else "_" for c in document_name
        )
        filename = f"{safe_name}_{timestamp}.html"

        # Organize by query set
        query_dir = self.download_dir / query_set_name
        query_dir.mkdir(parents=True, exist_ok=True)
        local_path = query_dir / filename

        # Write to disk
        local_path.write_bytes(content)

        # Create DocumentVersion
        doc_version = DocumentVersion(
            modified=modified,
            fetched_at=datetime.now(UTC),
            content_hash=f"sha256:{content_hash}",
            local_path=str(local_path),
        )

        return doc_version
