"""Configuration settings for QA generation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, cast

import structlog
import yaml
from pydantic import Field, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from docta.utils.constants import MAX_FILE_SIZE_BYTES
from qa_generation.models import (
    FilterConfig,
    GeneratorConfig,
    QueryDistribution,
)
from qa_generation.models.provider_config import EmbeddingConfig, LLMConfig
from qa_generation.models.qa_pair import ChangeType

logger = structlog.get_logger(__name__)


class QAGenerationSettings(BaseSettings):
    """Settings for QA generation loaded from YAML and environment variables.

    Settings are loaded in priority order:
    1. Environment variables (highest priority)
    2. YAML configuration file
    3. Default values (lowest priority)

    Environment variables are uppercase with no prefix.
    Examples: OPENAI_API_KEY, LLM_MODEL, LLM_PROVIDER, TESTSET_SIZE, SEED

    Note: API keys are only loaded from environment variables, never from YAML files.
    """

    model_config = SettingsConfigDict(
        env_prefix="",  # No prefix - use plain env var names
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    # API Keys (from environment only, never from config files)
    # Uses SecretStr to prevent leakage in logs, repr(), and serialization
    openai_api_key: SecretStr | None = Field(
        default=None,
        description="OpenAI API key (set via OPENAI_API_KEY env var)",
    )
    google_api_key: SecretStr | None = Field(
        default=None,
        description="Google API key (set via GOOGLE_API_KEY env var)",
    )

    # Generator configuration
    testset_size: int = Field(default=50, ge=1, le=10000, description="Number of QA pairs to generate")
    seed: int | None = Field(
        default=None,
        ge=0,
        le=2**31 - 1,
        description="Random seed for reproducibility (0 to 2^31-1)",
    )

    # LLM configuration
    llm_provider: str = Field(default="openai", description="LLM provider name")
    llm_model: str = Field(default="gpt-4o", description="LLM model name")
    llm_temperature: float = Field(default=0.3, ge=0.0, le=2.0, description="LLM temperature")
    llm_max_tokens: int | None = Field(default=None, ge=1, description="Max output tokens")

    # Embedding configuration
    embedding_provider: str = Field(default="openai", description="Embedding provider name")
    embedding_model: str = Field(default="text-embedding-3-small", description="Embedding model name")

    # Query distribution
    query_dist_specific: float = Field(default=0.5, ge=0.0, le=1.0, description="Specific query ratio")
    query_dist_abstract: float = Field(default=0.25, ge=0.0, le=1.0, description="Abstract query ratio")
    query_dist_comparative: float = Field(default=0.25, ge=0.0, le=1.0, description="Comparative query ratio")

    # Filtering configuration
    filter_min_text_length: int = Field(default=50, ge=0, description="Minimum text length")
    filter_max_text_length: int = Field(default=10000, ge=1, description="Maximum text length")
    filter_min_similarity: float = Field(default=0.0, ge=0.0, le=100.0, description="Minimum similarity")
    filter_max_similarity: float = Field(default=95.0, ge=0.0, le=100.0, description="Maximum similarity")
    filter_change_types: set[str] = Field(
        default_factory=lambda: {"text_change"},
        description="Change types to include",
    )

    @model_validator(mode="after")
    def validate_query_distribution_sum(self) -> "QAGenerationSettings":
        """Validate that query distribution sums to approximately 1.0."""
        total = self.query_dist_specific + self.query_dist_abstract + self.query_dist_comparative
        if abs(total - 1.0) >= 0.01:
            raise ValueError(
                f"Query distribution must sum to 1.0 (got {total:.3f}). "
                f"Adjust query_dist_specific={self.query_dist_specific}, "
                f"query_dist_abstract={self.query_dist_abstract}, "
                f"query_dist_comparative={self.query_dist_comparative}"
            )
        return self

    @model_validator(mode="after")
    def validate_filter_ranges(self) -> "QAGenerationSettings":
        """Validate that min values are less than or equal to max values."""
        if self.filter_min_text_length > self.filter_max_text_length:
            raise ValueError(f"filter_min_text_length ({self.filter_min_text_length}) must be <= " f"filter_max_text_length ({self.filter_max_text_length})")
        if self.filter_min_similarity > self.filter_max_similarity:
            raise ValueError(f"filter_min_similarity ({self.filter_min_similarity}) must be <= " f"filter_max_similarity ({self.filter_max_similarity})")
        return self

    def to_generator_config(self) -> GeneratorConfig:
        """Convert settings to GeneratorConfig model."""
        # Validate and convert set[str] to set[ChangeType] for type safety
        valid_change_types = {"text_change", "structure_change", "metadata_change", "document_added"}
        invalid_types = self.filter_change_types - valid_change_types
        if invalid_types:
            raise ValueError(f"Invalid change types: {invalid_types}. " f"Valid types: {valid_change_types}")
        change_types: set[ChangeType] = {cast(ChangeType, ct) for ct in self.filter_change_types}

        return GeneratorConfig(
            testset_size=self.testset_size,
            seed=self.seed,
            query_distribution=QueryDistribution(
                specific=self.query_dist_specific,
                abstract=self.query_dist_abstract,
                comparative=self.query_dist_comparative,
            ),
            filtering=FilterConfig(
                min_text_length=self.filter_min_text_length,
                max_text_length=self.filter_max_text_length,
                min_similarity=self.filter_min_similarity,
                max_similarity=self.filter_max_similarity,
                change_types=change_types,
            ),
            llm=LLMConfig(
                provider=self.llm_provider,
                model=self.llm_model,
                temperature=self.llm_temperature,
                max_tokens=self.llm_max_tokens,
            ),
            embedding=EmbeddingConfig(
                provider=self.embedding_provider,
                model=self.embedding_model,
            ),
        )

    def get_api_key(self, provider: str) -> str:
        """Get API key for a provider.

        Args:
            provider: Provider name (openai, google, gemini)

        Returns:
            API key string (secret value extracted)

        Raises:
            ValueError: If provider is not supported or API key is not set

        Note:
            'gemini' and 'google' both use the same GOOGLE_API_KEY env var
        """
        provider_lower = provider.lower()
        key_map = {
            "openai": self.openai_api_key,
            "google": self.google_api_key,
            "gemini": self.google_api_key,
        }

        # Check if provider is supported
        if provider_lower not in key_map:
            raise ValueError(f"Unsupported provider: '{provider}'. " f"Supported providers: {', '.join(key_map.keys())}")

        # Check if API key is set
        secret_key = key_map[provider_lower]
        if secret_key is None:
            env_var = "GOOGLE_API_KEY" if provider_lower in ("gemini", "google") else f"{provider_lower.upper()}_API_KEY"
            raise ValueError(f"API key not set for provider '{provider}'. " f"Set {env_var} environment variable.")

        return secret_key.get_secret_value()

    def setup_environment(self) -> None:
        """Set up environment variables for LLM/embedding providers.

        LiteLLM reads API keys from environment variables. This method sets
        the appropriate env vars based on configured providers.

        Should be called once after loading settings, before using generators.

        SECURITY NOTE: This writes API key secrets from SecretStr to os.environ
        as plaintext strings, making them accessible to all code in the process
        and any subprocesses. This is a known tradeoff required by LiteLLM's
        design. The secrets remain in os.environ for the process lifetime.

        For CLI tools that run once and exit, this is acceptable. For long-running
        services, consider alternative approaches or clear env vars after use.
        """

        # Set LLM provider API key
        llm_key = self.get_api_key(self.llm_provider)
        llm_env_var = self._get_env_var_name(self.llm_provider)
        os.environ[llm_env_var] = llm_key

        # Set embedding provider API key (may be same provider)
        embedding_key = self.get_api_key(self.embedding_provider)
        embedding_env_var = self._get_env_var_name(self.embedding_provider)
        os.environ[embedding_env_var] = embedding_key

        logger.info(
            "environment_setup_complete",
            llm_provider=self.llm_provider,
            embedding_provider=self.embedding_provider,
            llm_env_var=llm_env_var,
            embedding_env_var=embedding_env_var,
        )

    def _get_env_var_name(self, provider: str) -> str:
        """Get the environment variable name for a provider.

        Args:
            provider: Provider name (openai, google, gemini)

        Returns:
            Environment variable name (e.g., "OPENAI_API_KEY")

        Raises:
            ValueError: If provider is not supported
        """
        provider_lower = provider.lower()
        env_var_map = {
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
            "gemini": "GOOGLE_API_KEY",
        }

        env_var = env_var_map.get(provider_lower)
        if not env_var:
            raise ValueError(f"Unsupported provider: '{provider}'. " f"Supported: {', '.join(env_var_map.keys())}")

        return env_var


def load_settings_from_yaml(yaml_path: str | Path) -> dict[str, Any]:
    """Load settings from a YAML configuration file.

    Args:
        yaml_path: Path to YAML configuration file

    Returns:
        Dictionary of configuration values

    Raises:
        FileNotFoundError: If YAML file doesn't exist
        ValueError: If YAML file is too large (>10MB)
        yaml.YAMLError: If YAML is malformed
    """
    yaml_path = Path(yaml_path)

    if not yaml_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {yaml_path}")

    # YAML bomb protection - limit file size
    file_size = yaml_path.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"Config file too large: {file_size:,} bytes (max {MAX_FILE_SIZE_BYTES:,})")

    logger.info("loading_config_from_yaml", path=str(yaml_path), size_bytes=file_size)

    with yaml_path.open("r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)

    if config_data is None:
        logger.warning("empty_yaml_config", path=str(yaml_path))
        return {}

    # Flatten nested YAML structure to match settings field names
    flattened = {}

    # LLM config
    if "llm" in config_data:
        llm = config_data["llm"]
        flattened["llm_provider"] = llm.get("provider")
        flattened["llm_model"] = llm.get("model")
        flattened["llm_temperature"] = llm.get("temperature")
        flattened["llm_max_tokens"] = llm.get("max_tokens")

    # Embedding config
    if "embedding" in config_data:
        embedding = config_data["embedding"]
        flattened["embedding_provider"] = embedding.get("provider")
        flattened["embedding_model"] = embedding.get("model")

    # Generation config
    if "generation" in config_data:
        gen = config_data["generation"]
        flattened["testset_size"] = gen.get("testset_size")
        if "query_distribution" in gen:
            dist = gen["query_distribution"]
            flattened["query_dist_specific"] = dist.get("specific")
            flattened["query_dist_abstract"] = dist.get("abstract")
            flattened["query_dist_comparative"] = dist.get("comparative")

    # Filtering config
    if "filtering" in config_data:
        filt = config_data["filtering"]
        flattened["filter_min_text_length"] = filt.get("min_text_length")
        flattened["filter_max_text_length"] = filt.get("max_text_length")
        flattened["filter_min_similarity"] = filt.get("min_similarity")
        flattened["filter_max_similarity"] = filt.get("max_similarity")

        # Handle change_types - protect against single string instead of list
        change_types_raw = filt.get("change_types", ["text_change"])
        if isinstance(change_types_raw, str):
            # User provided a single string instead of a list - wrap it
            change_types_raw = [change_types_raw]
        flattened["filter_change_types"] = set(change_types_raw)

    # Remove None values
    flattened = {k: v for k, v in flattened.items() if v is not None}

    # Warn about unknown top-level keys (helps catch typos)
    known_top_keys = {"llm", "embedding", "generation", "filtering"}
    unknown = set(config_data.keys()) - known_top_keys
    if unknown:
        logger.warning("unknown_yaml_keys", keys=sorted(unknown), path=str(yaml_path))

    logger.info(
        "yaml_config_loaded",
        path=str(yaml_path),
        keys_loaded=list(flattened.keys()),
    )

    return flattened


def load_settings(
    yaml_path: str | Path | None = None,
    **overrides: Any,
) -> QAGenerationSettings:
    """Load QA generation settings from YAML file and environment.

    Args:
        yaml_path: Optional path to YAML configuration file
        **overrides: Additional settings to override

    Returns:
        QAGenerationSettings object

    Raises:
        ValidationError: If settings are invalid
    """
    config_dict = {}

    # Load from YAML if provided
    if yaml_path:
        try:
            config_dict.update(load_settings_from_yaml(yaml_path))
        except FileNotFoundError as e:
            logger.warning("yaml_config_not_found", path=str(yaml_path), error=str(e))
        except yaml.YAMLError as e:
            logger.error("yaml_config_invalid", path=str(yaml_path), error=str(e))
            raise

    # Apply overrides
    config_dict.update(overrides)

    # Create settings (environment variables take precedence)
    try:
        settings = QAGenerationSettings(**config_dict)
        logger.info(
            "settings_loaded",
            testset_size=settings.testset_size,
            llm_provider=settings.llm_provider,
            llm_model=settings.llm_model,
            has_openai_key=bool(settings.openai_api_key),
        )
        return settings
    except ValidationError as e:
        logger.error("settings_validation_failed", errors=e.errors())  # pylint: disable=no-member  # Pydantic ValidationError has errors() method
        raise
