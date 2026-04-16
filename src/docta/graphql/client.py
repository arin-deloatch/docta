"""GraphQL client with OAuth 2.0 authentication."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Optional

import requests
import structlog
from pydantic import HttpUrl, SecretStr

from docta.graphql.models import (
    DocumentationTitleNode,
    DocumentationTitlesResponse,
)


class GraphQLClient:  # pylint: disable=too-many-instance-attributes
    """GraphQL client with OAuth 2.0 Client Credentials flow and Apollo headers."""

    def __init__(
        self,
        *,
        endpoint: HttpUrl,
        api_scope: str,
        client_id: SecretStr,
        client_secret: SecretStr,
        token_url: HttpUrl,
        apollographql_client_name: SecretStr,
        apollographql_client_version: str = "latest",
        ssl_verify: bool | str = True,
        timeout: int = 30,
        retry_attempts: int = 3,
        retry_backoff: int = 30,
    ):
        """Initialize GraphQL client.

        Args:
            endpoint: GraphQL API base URL
            api_scope: OAuth 2.0 scope for API access (e.g., "api.graphql")
            client_id: OAuth 2.0 client ID
            client_secret: OAuth 2.0 client secret
            token_url: OAuth 2.0 token endpoint
            apollographql_client_name: Apollo client name header
            apollographql_client_version: Apollo client version header
            ssl_verify: SSL verification (bool or path to CA bundle)
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts
            retry_backoff: Backoff base in seconds (exponential)
        """
        self.endpoint = str(endpoint).rstrip("/")
        self.api_scope = api_scope
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = str(token_url)
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_backoff = retry_backoff
        self.logger = structlog.get_logger(__name__)

        # SSL configuration
        self.ssl_verify = ssl_verify

        # Session with Apollo headers
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "apollographql-client-name": apollographql_client_name.get_secret_value(),
                "apollographql-client-version": apollographql_client_version,
            }
        )

        # OAuth token management
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    def _get_access_token(self) -> str:
        """Get OAuth 2.0 access token using client credentials flow.

        Caches token and refreshes when expired.
        Refreshes 5 minutes before expiration to avoid edge cases.

        Returns:
            Valid access token

        Raises:
            requests.HTTPError: If token request fails
        """
        # Check if token is still valid
        if self._access_token and self._token_expires_at:
            # Refresh 5 minutes before expiration
            if datetime.now(UTC) < self._token_expires_at - timedelta(minutes=5):
                return self._access_token

        # Request new token
        self.logger.info("requesting_oauth_token", token_url=self.token_url, scope=self.api_scope)

        token_request_data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id.get_secret_value(),
            "client_secret": self.client_secret.get_secret_value(),
        }

        # Add scope if specified
        if self.api_scope:
            token_request_data["scope"] = self.api_scope

        response = requests.post(
            self.token_url,
            data=token_request_data,
            verify=self.ssl_verify,
            timeout=self.timeout,
        )
        response.raise_for_status()

        token_data = response.json()

        # Validate OAuth response structure
        if not isinstance(token_data, dict):
            raise ValueError("OAuth token response must be a dictionary")
        if "access_token" not in token_data:
            raise ValueError("OAuth token response missing 'access_token' field")
        if not isinstance(token_data["access_token"], str):
            raise ValueError("OAuth 'access_token' must be a string")

        access_token: str = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)  # Default 1 hour

        # Cache token and expiration
        self._access_token = access_token
        self._token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        self.logger.info("oauth_token_acquired", expires_in=expires_in)
        return access_token

    def execute_query(
        self,
        query: str,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute GraphQL query with OAuth authentication and retries.

        Args:
            query: GraphQL query string
            variables: Query variables

        Returns:
            GraphQL response data

        Raises:
            requests.HTTPError: If query fails after retries
        """
        payload = {"query": query, "variables": variables}

        for attempt in range(self.retry_attempts):
            try:
                # Get fresh access token
                access_token = self._get_access_token()

                # Execute query with Bearer token
                response = self.session.post(
                    self.endpoint,
                    json=payload,
                    headers={"Authorization": f"Bearer {access_token}"},
                    verify=self.ssl_verify,
                    timeout=self.timeout,
                )
                response.raise_for_status()

                result = response.json()

                # Validate GraphQL response structure
                if not isinstance(result, dict):
                    raise ValueError("GraphQL response must be a dictionary")

                # Check for GraphQL errors
                if "errors" in result:
                    error_msg = result["errors"]
                    self.logger.error("graphql_errors", errors=error_msg)
                    raise ValueError(f"GraphQL errors: {error_msg}")

                self.logger.debug("graphql_query_executed", attempt=attempt + 1)
                return result

            except requests.exceptions.RequestException as e:
                self.logger.warning(
                    "graphql_query_failed",
                    attempt=attempt + 1,
                    max_attempts=self.retry_attempts,
                    error=str(e),
                )

                # Don't retry on final attempt
                if attempt == self.retry_attempts - 1:
                    raise

                # Exponential backoff
                sleep_time = self.retry_backoff * (2**attempt)
                self.logger.info("retrying_after_backoff", sleep_seconds=sleep_time)
                time.sleep(sleep_time)

        # Should never reach here
        raise RuntimeError("Query failed after all retries")

    def parse_documentation_titles(
        self,
        response: dict,
    ) -> list[DocumentationTitleNode]:
        """Parse Relay-style response into DocumentationTitleNode list.

        Args:
            response: GraphQL response dict

        Returns:
            List of DocumentationTitleNode objects

        Raises:
            KeyError: If response structure is invalid
            ValueError: If response validation fails
        """
        try:
            # Validate response structure with Pydantic
            validated = DocumentationTitlesResponse(documentation_titles=response["data"]["documentation_titles"])

            # Extract nodes from edges
            nodes = [edge.node for edge in validated.documentation_titles.edges]

            self.logger.info("documentation_titles_parsed", count=len(nodes))
            return nodes

        except (KeyError, ValueError) as e:
            self.logger.error("response_parse_failed", error=str(e))
            raise

    def get_token_for_content_fetching(self) -> Callable[[], str]:
        """Get a callable that returns current access token.

        Returns a function that the ContentFetcher can call to get
        the current access token for fetching HTML content.

        Returns:
            Callable that returns valid access token
        """
        return self._get_access_token
