"""Unit tests for qa_generation.llm.provider module."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from qa_generation.llm.provider import (
    create_ragas_embeddings,
    create_ragas_llm,
    create_testset_generator,
)
from qa_generation.models.provider_config import EmbeddingConfig, LLMConfig


class TestCreateRagasLLM:
    """Tests for create_ragas_llm function."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("qa_generation.llm.provider.LangchainLLMWrapper")
    @patch("qa_generation.llm.provider.ChatOpenAI", create=True)
    def test_openai_provider(
        self,
        _mock_chat_openai: MagicMock,
        _mock_wrapper: MagicMock,
    ) -> None:
        """Test OpenAI provider creates a wrapped LLM."""
        with patch("qa_generation.llm.provider.create_ragas_llm") as mock_create:
            mock_create.return_value = MagicMock()
            config = LLMConfig(provider="openai", model="gpt-4o")
            result = mock_create(config)
            assert result is not None

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_openai_provider_real(self) -> None:
        """Test OpenAI provider with real create_ragas_llm call."""
        config = LLMConfig(provider="openai", model="gpt-4o")
        result = create_ragas_llm(config)
        assert result is not None

    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"})
    def test_google_provider(self) -> None:
        """Test Google provider creates an LLM."""
        config = LLMConfig(provider="google", model="gemini-pro")
        result = create_ragas_llm(config)
        assert result is not None

    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"})
    def test_gemini_provider(self) -> None:
        """Test gemini provider alias creates an LLM."""
        config = LLMConfig(provider="gemini", model="gemini-pro")
        result = create_ragas_llm(config)
        assert result is not None

    def test_unsupported_provider(self) -> None:
        """Test unsupported provider raises ValueError."""
        config = LLMConfig(provider="anthropic", model="claude")
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            create_ragas_llm(config)

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_openai_key(self) -> None:
        """Test missing OPENAI_API_KEY raises ValueError."""
        os.environ.pop("OPENAI_API_KEY", None)
        config = LLMConfig(provider="openai", model="gpt-4o")
        with pytest.raises(ValueError, match="OPENAI_API_KEY not found"):
            create_ragas_llm(config)

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_google_key(self) -> None:
        """Test missing GOOGLE_API_KEY raises ValueError."""
        os.environ.pop("GOOGLE_API_KEY", None)
        config = LLMConfig(provider="google", model="gemini-pro")
        with pytest.raises(ValueError, match="GOOGLE_API_KEY not found"):
            create_ragas_llm(config)


class TestCreateRagasEmbeddings:
    """Tests for create_ragas_embeddings function."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_openai_provider(self) -> None:
        """Test OpenAI provider creates embeddings."""
        config = EmbeddingConfig(provider="openai", model="text-embedding-3-small")
        result = create_ragas_embeddings(config)
        assert result is not None

    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"})
    def test_google_provider(self) -> None:
        """Test Google provider creates embeddings."""
        config = EmbeddingConfig(provider="google", model="embedding-001")
        result = create_ragas_embeddings(config)
        assert result is not None

    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"})
    def test_gemini_provider(self) -> None:
        """Test gemini provider alias creates embeddings."""
        config = EmbeddingConfig(provider="gemini", model="embedding-001")
        result = create_ragas_embeddings(config)
        assert result is not None

    def test_unsupported_provider(self) -> None:
        """Test unsupported embedding provider raises ValueError."""
        config = EmbeddingConfig(provider="cohere", model="embed")
        with pytest.raises(ValueError, match="Unsupported embeddings provider"):
            create_ragas_embeddings(config)

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_openai_key(self) -> None:
        """Test missing OPENAI_API_KEY raises ValueError for embeddings."""
        os.environ.pop("OPENAI_API_KEY", None)
        config = EmbeddingConfig(provider="openai")
        with pytest.raises(ValueError, match="OPENAI_API_KEY not found"):
            create_ragas_embeddings(config)

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_google_key(self) -> None:
        """Test missing GOOGLE_API_KEY raises ValueError for embeddings."""
        os.environ.pop("GOOGLE_API_KEY", None)
        config = EmbeddingConfig(provider="google")
        with pytest.raises(ValueError, match="GOOGLE_API_KEY not found"):
            create_ragas_embeddings(config)


class TestCreateTestsetGenerator:
    """Tests for create_testset_generator function."""

    @patch("qa_generation.llm.provider.TestsetGenerator")
    @patch("qa_generation.llm.provider.create_ragas_embeddings")
    @patch("qa_generation.llm.provider.create_ragas_llm")
    def test_creates_generator(
        self,
        mock_create_llm: MagicMock,
        mock_create_embeddings: MagicMock,
        mock_tsg_class: MagicMock,
    ) -> None:
        """Test testset generator is created with LLM and embeddings."""
        mock_llm = MagicMock()
        mock_emb = MagicMock()
        mock_create_llm.return_value = mock_llm
        mock_create_embeddings.return_value = mock_emb
        mock_tsg_instance = MagicMock()
        mock_tsg_class.return_value = mock_tsg_instance

        from pydantic import SecretStr

        from qa_generation.config.settings import QAGenerationSettings

        settings = QAGenerationSettings(
            openai_api_key=SecretStr("test-key"),
        )

        result = create_testset_generator(settings)
        assert result is mock_tsg_instance
        mock_tsg_class.assert_called_once_with(llm=mock_llm, embedding_model=mock_emb)
