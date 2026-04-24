# pylint: disable=protected-access,no-member
"""Unit tests for qa_generation.config.settings module."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from pydantic import SecretStr, ValidationError

from qa_generation.config.settings import (
    QAGenerationSettings,
    load_settings,
    load_settings_from_yaml,
)


@pytest.fixture(autouse=True)
def _isolate_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent BaseSettings from reading ambient env vars during settings tests."""
    for var in (
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "TESTSET_SIZE",
        "NUM_DOCUMENTS",
        "SEED",
        "LLM_PROVIDER",
        "LLM_MODEL",
        "LLM_TEMPERATURE",
        "LLM_MAX_TOKENS",
        "EMBEDDING_PROVIDER",
        "EMBEDDING_MODEL",
        "QUERY_DIST_SPECIFIC",
        "QUERY_DIST_ABSTRACT",
        "QUERY_DIST_COMPARATIVE",
        "FILTER_MIN_TEXT_LENGTH",
        "FILTER_MAX_TEXT_LENGTH",
        "FILTER_MIN_SIMILARITY",
        "FILTER_MAX_SIMILARITY",
        "FILTER_CHANGE_TYPES",
    ):
        monkeypatch.delenv(var, raising=False)


class TestQAGenerationSettings:
    """Tests for QAGenerationSettings model."""

    def test_defaults(self) -> None:
        """Test default settings values."""
        settings = QAGenerationSettings()
        assert settings.testset_size == 50
        assert settings.llm_provider == "openai"
        assert settings.llm_model == "gpt-4o"
        assert settings.query_dist_specific == 0.5

    def test_query_distribution_validation_pass(self) -> None:
        """Test valid query distribution weights are accepted."""
        settings = QAGenerationSettings(
            query_dist_specific=0.5,
            query_dist_abstract=0.3,
            query_dist_comparative=0.2,
        )
        assert settings.query_dist_specific == 0.5

    def test_query_distribution_validation_fail(self) -> None:
        """Test invalid query distribution weights raise validation error."""
        with pytest.raises(ValidationError, match="sum to 1.0"):
            QAGenerationSettings(
                query_dist_specific=0.5,
                query_dist_abstract=0.5,
                query_dist_comparative=0.5,
            )

    def test_filter_range_validation_pass(self) -> None:
        """Test valid filter ranges are accepted."""
        settings = QAGenerationSettings(
            filter_min_text_length=10,
            filter_max_text_length=100,
        )
        assert settings.filter_min_text_length == 10

    def test_filter_range_text_length_fail(self) -> None:
        """Test inverted text length range raises validation error."""
        with pytest.raises(ValidationError, match="filter_min_text_length"):
            QAGenerationSettings(
                filter_min_text_length=100,
                filter_max_text_length=50,
            )

    def test_filter_range_similarity_fail(self) -> None:
        """Test inverted similarity range raises validation error."""
        with pytest.raises(ValidationError, match="filter_min_similarity"):
            QAGenerationSettings(
                filter_min_similarity=90.0,
                filter_max_similarity=10.0,
            )

    def test_to_generator_config(self) -> None:
        """Test conversion to GeneratorConfig preserves all fields."""
        settings = QAGenerationSettings()
        config = settings.to_generator_config()
        assert config.testset_size == 50
        assert config.llm.provider == "openai"
        assert config.embedding.provider == "openai"
        assert config.query_distribution.specific == 0.5
        assert config.filtering.min_text_length == 50

    def test_to_generator_config_invalid_change_types(self) -> None:
        """Test invalid change types raise ValueError during conversion."""
        settings = QAGenerationSettings(
            filter_change_types={"invalid_type"},
        )
        with pytest.raises(ValueError, match="Invalid change types"):
            settings.to_generator_config()

    def test_get_api_key_openai(self) -> None:
        """Test retrieving OpenAI API key."""
        settings = QAGenerationSettings(
            openai_api_key=SecretStr("sk-test-key"),
        )
        assert settings.get_api_key("openai") == "sk-test-key"

    def test_get_api_key_google(self) -> None:
        """Test retrieving Google API key."""
        settings = QAGenerationSettings(
            google_api_key=SecretStr("google-key"),
        )
        assert settings.get_api_key("google") == "google-key"

    def test_get_api_key_gemini_uses_google(self) -> None:
        """Test gemini provider maps to Google API key."""
        settings = QAGenerationSettings(
            google_api_key=SecretStr("google-key"),
        )
        assert settings.get_api_key("gemini") == "google-key"

    def test_get_api_key_unsupported_provider(self) -> None:
        """Test unsupported provider raises ValueError."""
        settings = QAGenerationSettings()
        with pytest.raises(ValueError, match="Unsupported provider"):
            settings.get_api_key("anthropic")

    def test_get_api_key_not_set(self) -> None:
        """Test missing API key raises ValueError."""
        settings = QAGenerationSettings()
        with pytest.raises(ValueError, match="API key not set"):
            settings.get_api_key("openai")

    def test_setup_environment(self) -> None:
        """Test setup_environment sets OpenAI env var."""
        settings = QAGenerationSettings(
            openai_api_key=SecretStr("test-openai-key"),
            llm_provider="openai",
            embedding_provider="openai",
        )
        with patch.dict(os.environ, {}, clear=False):
            settings.setup_environment()
            assert os.environ["OPENAI_API_KEY"] == "test-openai-key"

    def test_setup_environment_google(self) -> None:
        """Test setup_environment sets Google env var."""
        settings = QAGenerationSettings(
            google_api_key=SecretStr("test-google-key"),
            llm_provider="google",
            embedding_provider="google",
        )
        with patch.dict(os.environ, {}, clear=False):
            settings.setup_environment()
            assert os.environ["GOOGLE_API_KEY"] == "test-google-key"

    def test_get_env_var_name(self) -> None:
        """Test environment variable name mapping for providers."""
        settings = QAGenerationSettings()
        assert settings._get_env_var_name("openai") == "OPENAI_API_KEY"
        assert settings._get_env_var_name("google") == "GOOGLE_API_KEY"
        assert settings._get_env_var_name("gemini") == "GOOGLE_API_KEY"

    def test_get_env_var_name_unsupported(self) -> None:
        """Test unsupported provider raises ValueError for env var name."""
        settings = QAGenerationSettings()
        with pytest.raises(ValueError, match="Unsupported provider"):
            settings._get_env_var_name("anthropic")

    def test_testset_size_bounds(self) -> None:
        """Test testset_size boundary values are validated."""
        QAGenerationSettings(testset_size=1)
        QAGenerationSettings(testset_size=10000)
        with pytest.raises(ValidationError):
            QAGenerationSettings(testset_size=0)
        with pytest.raises(ValidationError):
            QAGenerationSettings(testset_size=10001)


class TestLoadSettingsFromYaml:
    """Tests for load_settings_from_yaml function."""

    def test_load_valid_yaml(self, tmp_path: Path) -> None:
        """Test loading a valid YAML config file."""
        yaml_content = {
            "llm": {"provider": "google", "model": "gemini-pro"},
            "generation": {"testset_size": 100},
        }
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml.dump(yaml_content))

        result = load_settings_from_yaml(yaml_file)
        assert result["llm_provider"] == "google"
        assert result["llm_model"] == "gemini-pro"
        assert result["testset_size"] == 100

    def test_load_yaml_with_filtering(self, tmp_path: Path) -> None:
        """Test loading YAML with filtering configuration."""
        yaml_content = {
            "filtering": {
                "min_text_length": 100,
                "max_text_length": 5000,
                "change_types": ["text_change", "structure_change"],
            },
        }
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml.dump(yaml_content))

        result = load_settings_from_yaml(yaml_file)
        assert result["filter_min_text_length"] == 100
        assert result["filter_change_types"] == {"text_change", "structure_change"}

    def test_single_string_change_types_wrapped(self, tmp_path: Path) -> None:
        """Test single string change_types is wrapped into a set."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("filtering:\n  change_types: text_change\n")

        result = load_settings_from_yaml(yaml_file)
        assert result["filter_change_types"] == {"text_change"}

    def test_file_not_found(self) -> None:
        """Test missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            load_settings_from_yaml("/nonexistent/config.yaml")

    def test_empty_yaml(self, tmp_path: Path) -> None:
        """Test empty YAML file returns empty dict."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("")

        result = load_settings_from_yaml(yaml_file)
        assert result == {}

    def test_yaml_too_large(self, tmp_path: Path) -> None:
        """Test oversized YAML file raises ValueError."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("x" * (10_485_761))

        with pytest.raises(ValueError, match="too large"):
            load_settings_from_yaml(yaml_file)

    def test_query_distribution_loaded(self, tmp_path: Path) -> None:
        """Test query distribution values are loaded from YAML."""
        yaml_content = {
            "generation": {
                "query_distribution": {
                    "specific": 0.6,
                    "abstract": 0.2,
                    "comparative": 0.2,
                },
            },
        }
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml.dump(yaml_content))

        result = load_settings_from_yaml(yaml_file)
        assert result["query_dist_specific"] == 0.6

    def test_embedding_config_loaded(self, tmp_path: Path) -> None:
        """Test embedding configuration is loaded from YAML."""
        yaml_content = {
            "embedding": {"provider": "google", "model": "embedding-001"},
        }
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml.dump(yaml_content))

        result = load_settings_from_yaml(yaml_file)
        assert result["embedding_provider"] == "google"
        assert result["embedding_model"] == "embedding-001"

    def test_none_values_removed(self, tmp_path: Path) -> None:
        """Test None values are excluded from loaded settings."""
        yaml_content = {
            "llm": {"provider": "openai"},
        }
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml.dump(yaml_content))

        result = load_settings_from_yaml(yaml_file)
        assert "llm_provider" in result
        assert "llm_model" not in result


class TestLoadSettings:
    """Tests for load_settings function."""

    def test_load_with_defaults(self) -> None:
        """Test loading settings with default values."""
        settings = load_settings()
        assert settings.testset_size == 50
        assert settings.llm_provider == "openai"

    def test_load_with_overrides(self) -> None:
        """Test loading settings with keyword overrides."""
        settings = load_settings(testset_size=100, llm_provider="google")
        assert settings.testset_size == 100
        assert settings.llm_provider == "google"

    def test_load_with_yaml(self, tmp_path: Path) -> None:
        """Test loading settings from a YAML file."""
        yaml_content = {"generation": {"testset_size": 200}}
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml.dump(yaml_content))

        settings = load_settings(yaml_path=yaml_file)
        assert settings.testset_size == 200

    def test_overrides_take_precedence_over_yaml(self, tmp_path: Path) -> None:
        """Test keyword overrides take precedence over YAML values."""
        yaml_content = {"generation": {"testset_size": 200}}
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml.dump(yaml_content))

        settings = load_settings(yaml_path=yaml_file, testset_size=300)
        assert settings.testset_size == 300

    def test_missing_yaml_continues(self) -> None:
        """Test missing YAML file falls back to defaults."""
        settings = load_settings(yaml_path="/nonexistent/config.yaml")
        assert settings.testset_size == 50

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        """Test invalid YAML content raises YAMLError."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(": invalid yaml: [[[")

        with pytest.raises(yaml.YAMLError):
            load_settings(yaml_path=yaml_file)

    def test_invalid_settings_raises(self) -> None:
        """Test invalid settings values raise ValidationError."""
        with pytest.raises(ValidationError):
            load_settings(testset_size=0)
