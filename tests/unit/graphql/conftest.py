"""Shared fixtures for GraphQL tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest


@pytest.fixture
def sample_timestamp() -> datetime:
    """Fixture providing a fixed timestamp for testing."""
    return datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def sample_graphql_yaml_content() -> str:
    """Fixture providing sample GraphQL configuration YAML."""
    return """
graphql:
  endpoint: https://api.example.com/graphql
  api_scope: api.graphql
  apollographql_client_version: latest
  ssl:
    verify: true
  polling:
    interval_minutes: 60
    initial_delay_seconds: 10
    retry_attempts: 3
    retry_backoff_seconds: 30
    timeout_seconds: 30
  query_sets:
    - name: test_query_set
      enabled: true
      query: |
        query TestQuery {
          documentation_titles {
            edges {
              node {
                name
              }
            }
          }
        }
      variables: {}
      pipeline:
        version_label: v1.0.0
        output_dir: output/test
        run_qa_generation: false
        qa_config: config/system.yaml
        max_concurrent_fetches: 10

state:
  file_path: config/state/test_state.json
  backup_enabled: true
  backup_count: 5

content:
  download_dir: data/fetched_content
  max_file_size_mb: 100
  timeout_seconds: 60
  verify_ssl: true

logging:
  level: INFO
  file:
    enabled: false
  console:
    enabled: true
    format: json
"""


@pytest.fixture
def sample_graphql_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture providing sample environment variables for GraphQL."""
    monkeypatch.setenv("GRAPHQL_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("GRAPHQL_CLIENT_SECRET", "test_client_secret")
    monkeypatch.setenv("GRAPHQL_TOKEN_URL", "https://auth.example.com/token")
    monkeypatch.setenv("APOLLOGRAPHQL_CLIENT_NAME", "test_client")


@pytest.fixture
def sample_graphql_yaml_file(
    tmp_path: Path,
    sample_graphql_yaml_content: str,  # pylint: disable=redefined-outer-name  # pytest fixture injection
) -> Path:
    """Fixture creating a temporary GraphQL config YAML file."""
    yaml_file = tmp_path / "graphql_config.yaml"
    yaml_file.write_text(sample_graphql_yaml_content)
    return yaml_file
