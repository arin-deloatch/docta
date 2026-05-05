"""Framework-agnostic LLM and embedding managers using litellm."""

from __future__ import annotations

import os
from typing import Any, Literal

import structlog

from qa_generation.llm.constants import (
    LITELLM_MODEL_PREFIX,
    PROVIDER_ENV_VAR,
    VALID_CHAT_MODEL_PREFIXES,
    VALID_EMBEDDING_MODEL_PREFIXES,
)
from qa_generation.models.provider_config import EmbeddingConfig, LLMConfig

logger = structlog.get_logger(__name__)

_CAPABILITY_PREFIX_MAP = {
    "chat": VALID_CHAT_MODEL_PREFIXES,
    "embedding": VALID_EMBEDDING_MODEL_PREFIXES,
}


def _validate_model_name(model: str, provider: str, capability: Literal["chat", "embedding"]) -> None:
    valid_prefixes = _CAPABILITY_PREFIX_MAP[capability].get(provider, [])
    if valid_prefixes and not any(model.lower().startswith(p) for p in valid_prefixes):
        raise ValueError(
            f"Model '{model}' does not match any known {capability} model prefix for provider '{provider}'. "
            f"Expected one of: {valid_prefixes}. Update VALID_CHAT_MODEL_PREFIXES or "
            f"VALID_EMBEDDING_MODEL_PREFIXES in constants.py if this is a newly released model."
        )


class LLMManager:
    """Manages litellm LLM configuration independent of any evaluation framework.

    Validates that the required API key is present in the environment and
    provides a litellm-formatted model name and inference parameters that
    framework adapters (e.g. RagasLLMManager) can consume.
    """

    def __init__(self, config: LLMConfig) -> None:
        """Initialize and validate environment for the given LLM config.

        Args:
            config: LLM provider, model, temperature, and optional max_tokens.

        Raises:
            ValueError: If the provider is unsupported, its API key is absent,
                        or the model name doesn't match a known prefix.
        """
        self._config = config
        self._validate_env()

    def _validate_env(self) -> None:
        provider = self._config.provider.lower()
        env_vars = PROVIDER_ENV_VAR.get(provider)
        if env_vars is None:
            raise ValueError(f"Unsupported provider: '{self._config.provider}'. Supported: {list(PROVIDER_ENV_VAR)}")
        if not any(os.environ.get(v) for v in env_vars):
            raise ValueError(f"None of {list(env_vars)} found in environment for provider '{self._config.provider}'.")
        _validate_model_name(self._config.model, provider, "chat")

    def get_model_name(self) -> str:
        """Return the litellm-formatted model name (e.g. 'gpt-4o' or 'gemini/gemini-2.0-flash-exp')."""
        prefix = LITELLM_MODEL_PREFIX.get(self._config.provider.lower(), "")
        return f"{prefix}{self._config.model}"

    def get_llm_params(self) -> dict[str, Any]:
        """Return inference parameters for litellm (temperature, optional max_tokens)."""
        params: dict[str, Any] = {"temperature": self._config.temperature}
        if self._config.max_tokens is not None:
            params["max_tokens"] = self._config.max_tokens
        return params

    def get_provider(self) -> str:
        """Return the normalized (lowercase) provider name."""
        return self._config.provider.lower()


class EmbeddingManager:
    """Manages litellm embedding configuration independent of any evaluation framework.

    Validates the required API key and model name, and provides a litellm-formatted
    model name for use by framework embedding adapters (e.g. RagasEmbeddingManager).
    """

    def __init__(self, config: EmbeddingConfig) -> None:
        """Initialize and validate environment for the given embedding config.

        Args:
            config: Embedding provider and model name.

        Raises:
            ValueError: If the provider is unsupported, its API key is absent,
                        or the model name doesn't match a known prefix.
        """
        self._config = config
        self._validate_env()

    def _validate_env(self) -> None:
        provider = self._config.provider.lower()
        env_vars = PROVIDER_ENV_VAR.get(provider)
        if env_vars is None:
            raise ValueError(f"Unsupported embedding provider: '{self._config.provider}'. Supported: {list(PROVIDER_ENV_VAR)}")
        if not any(os.environ.get(v) for v in env_vars):
            raise ValueError(f"None of {list(env_vars)} found in environment for embedding provider '{self._config.provider}'.")
        _validate_model_name(self._config.model, provider, "embedding")

    def get_model_name(self) -> str:
        """Return the litellm-formatted embedding model name."""
        prefix = LITELLM_MODEL_PREFIX.get(self._config.provider.lower(), "")
        return f"{prefix}{self._config.model}"
