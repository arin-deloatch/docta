"""
GraphQL Polling Service for Doc-Diff-Tracker.

This module provides continuous monitoring of GraphQL APIs for documentation changes
and automatically triggers the diff + QA generation pipeline when changes are detected.

Main components:
    - client: GraphQL client with authentication and retry logic
    - fetcher: HTTP client for fetching HTML content from URLs
    - models: Pydantic models for GraphQL responses and configuration
    - state: State persistence with file locking and atomic writes
    - scheduler: Async polling loop orchestrator
    - pipeline: Pipeline runner that invokes diff/QA generation
    - config: Configuration loading from YAML and environment variables
"""

from docta.graphql.client import GraphQLClient
from docta.graphql.config import load_graphql_settings
from docta.graphql.fetcher import ContentFetcher
from docta.graphql.models import (
    DocumentState,
    DocumentVersion,
    GraphQLPollingSettings,
    PollingState,
    QuerySetConfig,
)
from docta.graphql.state import StateManager

__version__ = "1.0.0"

__all__ = [
    "GraphQLClient",
    "ContentFetcher",
    "StateManager",
    "load_graphql_settings",
    "GraphQLPollingSettings",
    "PollingState",
    "DocumentState",
    "DocumentVersion",
    "QuerySetConfig",
]
