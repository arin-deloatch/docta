# pylint: disable=redefined-outer-name
"""Unit tests for LLMManager and EmbeddingManager."""

from __future__ import annotations

import pytest

from qa_generation.llm.constants import VALID_CHAT_MODEL_PREFIXES
from qa_generation.llm.manager import EmbeddingManager, LLMManager
from qa_generation.models.provider_config import EmbeddingConfig, LLMConfig

# ---------------------------------------------------------------------------
# LLMManager
# ---------------------------------------------------------------------------


class TestLLMManagerModelName:
    """Test litellm model name construction per provider."""

    def test_openai_model_name_has_no_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OpenAI models are passed to litellm without any provider prefix."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        manager = LLMManager(LLMConfig(provider="openai", model="gpt-4o"))
        assert manager.get_model_name() == "gpt-4o"

    def test_gemini_model_name_has_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Gemini models are prefixed with 'gemini/' for litellm routing."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        manager = LLMManager(LLMConfig(provider="gemini", model="gemini-2.0-flash-exp"))
        assert manager.get_model_name() == "gemini/gemini-2.0-flash-exp"

    def test_google_alias_has_gemini_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The 'google' provider alias produces the same 'gemini/' prefix as 'gemini'."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        manager = LLMManager(LLMConfig(provider="google", model="gemini-1.5-pro"))
        assert manager.get_model_name() == "gemini/gemini-1.5-pro"


class TestLLMManagerValidation:
    """Test provider and model name validation at construction time."""

    def test_missing_api_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Construction fails with a ValueError listing the missing env vars when the API key is absent."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(ValueError, match="None of.*OPENAI_API_KEY"):
            LLMManager(LLMConfig(provider="openai", model="gpt-4o"))

    def test_gemini_api_key_accepted_for_gemini_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GEMINI_API_KEY alone is sufficient for the gemini provider (litellm alias)."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        manager = LLMManager(LLMConfig(provider="gemini", model="gemini-2.0-flash-exp"))
        assert manager.get_model_name() == "gemini/gemini-2.0-flash-exp"

    def test_gemini_both_keys_absent_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Construction fails when neither GOOGLE_API_KEY nor GEMINI_API_KEY is set."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(ValueError, match="None of.*GOOGLE_API_KEY.*GEMINI_API_KEY"):
            LLMManager(LLMConfig(provider="gemini", model="gemini-2.0-flash-exp"))

    def test_unsupported_provider_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Construction fails with a ValueError when the provider is not in the supported set."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        with pytest.raises(ValueError, match="Unsupported provider"):
            LLMManager(LLMConfig(provider="anthropic", model="claude-3"))

    def test_invalid_model_name_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Construction fails when the model name does not start with any known prefix for that provider."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        with pytest.raises(ValueError, match="does not match any known chat model prefix"):
            LLMManager(LLMConfig(provider="openai", model="claude-3-opus"))

    def test_invalid_model_name_includes_expected_prefixes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The ValueError for an invalid model name lists the valid prefixes for that provider."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        with pytest.raises(ValueError, match="gpt-"):
            LLMManager(LLMConfig(provider="openai", model="llama-3"))

    def test_new_model_prefix_in_constants_unblocks_validation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Demonstrates how to unblock a newly released model family."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        original = VALID_CHAT_MODEL_PREFIXES["openai"][:]
        VALID_CHAT_MODEL_PREFIXES["openai"].append("o4")
        try:
            manager = LLMManager(LLMConfig(provider="openai", model="o4-mini"))
            assert manager.get_model_name() == "o4-mini"
        finally:
            VALID_CHAT_MODEL_PREFIXES["openai"] = original

    def test_embedding_model_in_llm_config_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LLMManager rejects embedding model names that don't match any chat model prefix."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        with pytest.raises(ValueError, match="does not match any known chat model prefix"):
            LLMManager(LLMConfig(provider="openai", model="text-embedding-3-small"))


class TestLLMManagerParams:
    """Test inference parameter dict construction."""

    def test_params_include_temperature(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_llm_params returns a dict containing the configured temperature value."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        manager = LLMManager(LLMConfig(provider="openai", model="gpt-4o", temperature=0.7))
        assert manager.get_llm_params()["temperature"] == 0.7

    def test_params_include_max_tokens_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_llm_params includes max_tokens when an explicit value is configured."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        manager = LLMManager(LLMConfig(provider="openai", model="gpt-4o", max_tokens=1024))
        params = manager.get_llm_params()
        assert params["max_tokens"] == 1024

    def test_params_omit_max_tokens_when_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_llm_params omits the max_tokens key entirely when the config value is None."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        manager = LLMManager(LLMConfig(provider="openai", model="gpt-4o", max_tokens=None))
        assert "max_tokens" not in manager.get_llm_params()

    def test_get_provider_returns_lowercase(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_provider normalises the provider name to lowercase regardless of input casing."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        manager = LLMManager(LLMConfig(provider="OpenAI", model="gpt-4o"))
        assert manager.get_provider() == "openai"


# ---------------------------------------------------------------------------
# EmbeddingManager
# ---------------------------------------------------------------------------


class TestEmbeddingManagerModelName:
    """Test litellm embedding model name construction per provider."""

    def test_openai_embedding_has_no_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OpenAI embedding models are passed to litellm without any provider prefix."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        manager = EmbeddingManager(EmbeddingConfig(provider="openai", model="text-embedding-3-small"))
        assert manager.get_model_name() == "text-embedding-3-small"

    def test_gemini_embedding_has_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Gemini embedding models are prefixed with 'gemini/' for litellm routing."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        manager = EmbeddingManager(EmbeddingConfig(provider="gemini", model="gemini-embedding-001"))
        assert manager.get_model_name() == "gemini/gemini-embedding-001"

    def test_google_alias_embedding_has_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The 'google' provider alias produces the same 'gemini/' prefix for embedding models."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        manager = EmbeddingManager(EmbeddingConfig(provider="google", model="text-embedding-004"))
        assert manager.get_model_name() == "gemini/text-embedding-004"


class TestEmbeddingManagerValidation:
    """Test provider and model name validation for embeddings."""

    def test_missing_api_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Construction fails with a ValueError listing the missing env vars when the API key is absent."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(ValueError, match="None of.*OPENAI_API_KEY"):
            EmbeddingManager(EmbeddingConfig(provider="openai", model="text-embedding-3-small"))

    def test_gemini_api_key_accepted_for_gemini_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GEMINI_API_KEY alone is sufficient for the gemini embedding provider (litellm alias)."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        manager = EmbeddingManager(EmbeddingConfig(provider="gemini", model="gemini-embedding-001"))
        assert manager.get_model_name() == "gemini/gemini-embedding-001"

    def test_unsupported_provider_raises(self) -> None:
        """Construction fails with a ValueError when the embedding provider is not in the supported set."""
        with pytest.raises(ValueError, match="Unsupported embedding provider"):
            EmbeddingManager(EmbeddingConfig(provider="anthropic", model="claude-embed"))

    def test_invalid_model_name_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Construction fails when the embedding model name does not match any known prefix for that provider."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        with pytest.raises(ValueError, match="does not match any known embedding model prefix"):
            EmbeddingManager(EmbeddingConfig(provider="openai", model="ada-002"))

    def test_chat_model_in_embedding_config_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """EmbeddingManager rejects chat model names that don't match any embedding model prefix."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        with pytest.raises(ValueError, match="does not match any known embedding model prefix"):
            EmbeddingManager(EmbeddingConfig(provider="openai", model="gpt-4o"))
