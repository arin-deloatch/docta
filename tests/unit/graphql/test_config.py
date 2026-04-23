"""Unit tests for docta.graphql.config module."""

from __future__ import annotations

from pathlib import Path

import pytest

from docta.graphql.config import load_graphql_settings
from docta.graphql.models import GraphQLPollingSettings


class TestLoadGraphQLSettings:
    """Tests for load_graphql_settings function."""

    def test_load_settings_from_yaml(
        self,
        sample_graphql_yaml_file: Path,
        sample_graphql_env_vars: None,  # pylint: disable=unused-argument  # Fixture sets env vars via side effect
    ) -> None:
        """Test loading settings from YAML file."""
        _ = sample_graphql_env_vars  # Acknowledge side-effect fixture
        settings = load_graphql_settings(sample_graphql_yaml_file)

        assert isinstance(settings, GraphQLPollingSettings)
        assert str(settings.graphql.endpoint) == "https://api.example.com/graphql"
        assert settings.graphql.polling.interval_minutes == 60
        assert len(settings.graphql.query_sets) == 1
        assert settings.graphql.query_sets[0].name == "test_query_set"

    def test_load_settings_with_env_vars(
        self,
        sample_graphql_yaml_file: Path,
        sample_graphql_env_vars: None,  # pylint: disable=unused-argument  # Fixture sets env vars via side effect
    ) -> None:
        """Test that environment variables are loaded."""
        _ = sample_graphql_env_vars  # Acknowledge side-effect fixture
        settings = load_graphql_settings(sample_graphql_yaml_file)

        # SecretStr values need to be accessed with .get_secret_value()
        assert settings.graphql_client_id.get_secret_value() == "test_client_id"
        assert settings.graphql_client_secret.get_secret_value() == "test_client_secret"
        assert str(settings.graphql_token_url) == "https://auth.example.com/token"
        assert settings.apollographql_client_name.get_secret_value() == "test_client"

    def test_load_settings_without_yaml(
        self,
        sample_graphql_env_vars: None,  # pylint: disable=unused-argument  # Fixture sets env vars via side effect
    ) -> None:
        """Test loading settings without YAML file (env vars + defaults)."""
        _ = sample_graphql_env_vars  # Acknowledge side-effect fixture
        # This will fail because graphql config is required
        with pytest.raises(ValueError, match="validation"):
            load_graphql_settings(None)

    def test_nonexistent_yaml_file(self) -> None:
        """Test that nonexistent YAML file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="not found"):
            load_graphql_settings("/nonexistent/config.yaml")

    def test_yaml_file_too_large(
        self,
        tmp_path: Path,
        sample_graphql_env_vars: None,  # pylint: disable=unused-argument  # Fixture sets env vars via side effect
    ) -> None:
        """Test that oversized YAML file raises ValueError."""
        _ = sample_graphql_env_vars  # Acknowledge side-effect fixture
        large_file = tmp_path / "large.yaml"
        # Create a file larger than MAX_FILE_SIZE_BYTES (10MB)
        large_file.write_text("x" * (11 * 1024 * 1024))

        with pytest.raises(ValueError, match="too large"):
            load_graphql_settings(large_file)

    def test_invalid_yaml_syntax(self, tmp_path: Path) -> None:
        """Test that invalid YAML syntax raises ValueError."""
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("invalid:\n  - yaml\n  missing_colon")

        with pytest.raises(ValueError, match="Invalid YAML"):
            load_graphql_settings(bad_yaml)

    def test_invalid_configuration(
        self,
        tmp_path: Path,
        sample_graphql_env_vars: None,  # pylint: disable=unused-argument  # Fixture sets env vars via side effect
    ) -> None:
        """Test that invalid configuration raises ValueError."""
        _ = sample_graphql_env_vars  # Acknowledge side-effect fixture
        invalid_yaml = tmp_path / "invalid.yaml"
        invalid_yaml.write_text("""
graphql:
  endpoint: not_a_url
  query_sets: []
""")

        with pytest.raises(ValueError, match="validation"):
            load_graphql_settings(invalid_yaml)

    def test_settings_with_overrides(
        self,
        sample_graphql_yaml_file: Path,
        sample_graphql_env_vars: None,  # pylint: disable=unused-argument  # Fixture sets env vars via side effect
    ) -> None:
        """Test loading settings with override parameters."""
        _ = sample_graphql_env_vars  # Acknowledge side-effect fixture
        settings = load_graphql_settings(
            sample_graphql_yaml_file,
            logging={"level": "DEBUG"},
        )

        assert settings.logging.level == "DEBUG"  # pylint: disable=no-member  # Pydantic model field

    def test_minimal_valid_config(
        self,
        tmp_path: Path,
        sample_graphql_env_vars: None,  # pylint: disable=unused-argument  # Fixture sets env vars via side effect
    ) -> None:
        """Test minimal valid configuration."""
        _ = sample_graphql_env_vars  # Acknowledge side-effect fixture
        minimal_yaml = tmp_path / "minimal.yaml"
        minimal_yaml.write_text("""
graphql:
  endpoint: https://api.example.com/graphql
  query_sets:
    - name: test
      query: "query { test }"
      variables: {}
      pipeline:
        version_label: v1
        output_dir: output
""")

        settings = load_graphql_settings(minimal_yaml)
        assert str(settings.graphql.endpoint) == "https://api.example.com/graphql"
        assert len(settings.graphql.query_sets) == 1

    def test_state_config_defaults(
        self,
        sample_graphql_yaml_file: Path,
        sample_graphql_env_vars: None,  # pylint: disable=unused-argument  # Fixture sets env vars via side effect
    ) -> None:
        """Test that state config has proper defaults."""
        settings = load_graphql_settings(sample_graphql_yaml_file)

        assert settings.state.file_path == "config/state/test_state.json"  # pylint: disable=no-member  # Pydantic model field
        assert settings.state.backup_enabled is True  # pylint: disable=no-member  # Pydantic model field
        assert settings.state.backup_count == 5  # pylint: disable=no-member  # Pydantic model field

    def test_content_config_defaults(
        self,
        sample_graphql_yaml_file: Path,
        sample_graphql_env_vars: None,  # pylint: disable=unused-argument  # Fixture sets env vars via side effect
    ) -> None:
        """Test that content config has proper defaults."""
        settings = load_graphql_settings(sample_graphql_yaml_file)

        assert settings.content.download_dir == "data/fetched_content"  # pylint: disable=no-member  # Pydantic model field
        assert settings.content.max_file_size_mb == 100  # pylint: disable=no-member  # Pydantic model field
        assert settings.content.verify_ssl is True  # pylint: disable=no-member  # Pydantic model field

    def test_logging_config_from_yaml(
        self,
        sample_graphql_yaml_file: Path,
        sample_graphql_env_vars: None,  # pylint: disable=unused-argument  # Fixture sets env vars via side effect
    ) -> None:
        """Test logging configuration from YAML."""
        settings = load_graphql_settings(sample_graphql_yaml_file)

        assert settings.logging.level == "INFO"  # pylint: disable=no-member  # Pydantic model field
        assert settings.logging.file.enabled is False  # pylint: disable=no-member  # Pydantic model field
        assert settings.logging.console.enabled is True  # pylint: disable=no-member  # Pydantic model field
        assert settings.logging.console.format == "json"  # pylint: disable=no-member  # Pydantic model field

    def test_multiple_query_sets(
        self,
        tmp_path: Path,
        sample_graphql_env_vars: None,  # pylint: disable=unused-argument  # Fixture sets env vars via side effect
    ) -> None:
        """Test configuration with multiple query sets."""
        multi_yaml = tmp_path / "multi.yaml"
        multi_yaml.write_text("""
graphql:
  endpoint: https://api.example.com/graphql
  query_sets:
    - name: query_set_1
      query: "query { test1 }"
      variables: {}
      pipeline:
        version_label: v1
        output_dir: output1
    - name: query_set_2
      enabled: false
      query: "query { test2 }"
      variables: {"var": "value"}
      pipeline:
        version_label: v2
        output_dir: output2
""")

        settings = load_graphql_settings(multi_yaml)
        assert len(settings.graphql.query_sets) == 2
        assert settings.graphql.query_sets[0].name == "query_set_1"
        assert settings.graphql.query_sets[1].name == "query_set_2"
        assert settings.graphql.query_sets[1].enabled is False
        assert settings.graphql.query_sets[1].variables == {"var": "value"}

    def test_ssl_config_from_yaml(
        self,
        tmp_path: Path,
        sample_graphql_env_vars: None,  # pylint: disable=unused-argument  # Fixture sets env vars via side effect
    ) -> None:
        """Test SSL configuration from YAML."""
        ssl_yaml = tmp_path / "ssl.yaml"
        ssl_yaml.write_text("""
graphql:
  endpoint: https://api.example.com/graphql
  ssl:
    verify: false
    cert_path: /path/to/cert.pem
  query_sets:
    - name: test
      query: "query { test }"
      variables: {}
      pipeline:
        version_label: v1
        output_dir: output
""")

        settings = load_graphql_settings(ssl_yaml)
        assert settings.graphql.ssl.verify is False
        assert settings.graphql.ssl.cert_path == "/path/to/cert.pem"

    def test_polling_config_from_yaml(
        self,
        tmp_path: Path,
        sample_graphql_env_vars: None,  # pylint: disable=unused-argument  # Fixture sets env vars via side effect
    ) -> None:
        """Test polling configuration from YAML."""
        polling_yaml = tmp_path / "polling.yaml"
        polling_yaml.write_text("""
graphql:
  endpoint: https://api.example.com/graphql
  polling:
    interval_minutes: 120
    initial_delay_seconds: 30
    retry_attempts: 5
    retry_backoff_seconds: 60
    timeout_seconds: 45
  query_sets:
    - name: test
      query: "query { test }"
      variables: {}
      pipeline:
        version_label: v1
        output_dir: output
""")

        settings = load_graphql_settings(polling_yaml)
        assert settings.graphql.polling.interval_minutes == 120
        assert settings.graphql.polling.initial_delay_seconds == 30
        assert settings.graphql.polling.retry_attempts == 5
        assert settings.graphql.polling.retry_backoff_seconds == 60
        assert settings.graphql.polling.timeout_seconds == 45


class TestConfigEdgeCases:
    """Test edge cases for configuration loading."""

    def test_empty_yaml_file(
        self,
        tmp_path: Path,
        sample_graphql_env_vars: None,  # pylint: disable=unused-argument  # Fixture sets env vars via side effect
    ) -> None:
        """Test loading from empty YAML file."""
        empty_yaml = tmp_path / "empty.yaml"
        empty_yaml.write_text("")

        with pytest.raises(ValueError, match="validation"):
            load_graphql_settings(empty_yaml)

    def test_yaml_with_only_comments(
        self,
        tmp_path: Path,
        sample_graphql_env_vars: None,  # pylint: disable=unused-argument  # Fixture sets env vars via side effect
    ) -> None:
        """Test loading from YAML with only comments."""
        comment_yaml = tmp_path / "comments.yaml"
        comment_yaml.write_text("# This is a comment\n# Another comment\n")

        with pytest.raises(ValueError, match="validation"):
            load_graphql_settings(comment_yaml)

    def test_missing_required_env_vars(
        self,
        sample_graphql_yaml_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that missing required env vars causes validation error."""
        for var in (
            "GRAPHQL_CLIENT_ID",
            "GRAPHQL_CLIENT_SECRET",
            "GRAPHQL_TOKEN_URL",
            "APOLLOGRAPHQL_CLIENT_NAME",
        ):
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(ValueError, match="validation"):
            load_graphql_settings(sample_graphql_yaml_file)

    def test_optional_cert_path_env_var(
        self,
        sample_graphql_yaml_file: Path,
        sample_graphql_env_vars: None,  # pylint: disable=unused-argument  # Fixture sets env vars via side effect
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test optional cert path environment variable."""
        monkeypatch.setenv("GRAPHQL_CERT_PATH", "/custom/cert.pem")

        settings = load_graphql_settings(sample_graphql_yaml_file)
        assert settings.graphql_cert_path == "/custom/cert.pem"
