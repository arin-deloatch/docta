"""Factory for creating litellm-backed LLM and embedding providers for RAGAS.

Delegates to LLMManager / EmbeddingManager (framework-agnostic) and
RagasLLMManager / RagasEmbeddingManager (RAGAS adapters).
"""

from __future__ import annotations

from typing import Any

import structlog
from ragas.testset import TestsetGenerator

from qa_generation.config.settings import QAGenerationSettings
from qa_generation.llm.manager import EmbeddingManager, LLMManager
from qa_generation.llm.ragas import RagasEmbeddingManager, RagasLLMManager
from qa_generation.models.provider_config import EmbeddingConfig, LLMConfig

logger = structlog.get_logger(__name__)


def create_ragas_llm(config: LLMConfig) -> Any:
    """Create a RAGAS LLM instance backed by litellm.

    API keys must be set in environment before calling.
    Use QAGenerationSettings.setup_environment() to configure.

    Args:
        config: LLM configuration (provider, model, temperature, max_tokens).

    Returns:
        RAGAS-compatible LLM (InstructorBaseRagasLLM via litellm).

    Raises:
        ValueError: If provider is unsupported, API key is missing, or model name is invalid.
        ImportError: If litellm, instructor, or ragas packages are not installed.
    """
    logger.info("creating_ragas_llm", provider=config.provider, model=config.model, temperature=config.temperature)
    return RagasLLMManager(LLMManager(config)).get_llm()


def create_ragas_embeddings(config: EmbeddingConfig) -> Any:
    """Create a RAGAS embeddings instance backed by litellm.

    API keys must be set in environment before calling.
    Use QAGenerationSettings.setup_environment() to configure.

    Args:
        config: Embedding configuration (provider, model).

    Returns:
        RAGAS-compatible embeddings (LiteLLMEmbeddings).

    Raises:
        ValueError: If provider is unsupported, API key is missing, or model name is invalid.
        ImportError: If litellm or ragas packages are not installed.
    """
    logger.info("creating_ragas_embeddings", provider=config.provider, model=config.model)
    return RagasEmbeddingManager(EmbeddingManager(config)).get_embeddings()


def create_testset_generator(settings: QAGenerationSettings) -> TestsetGenerator:
    """Create a configured RAGAS TestsetGenerator using the litellm backend.

    IMPORTANT: Call settings.setup_environment() before using this function
    to ensure API keys are set in environment variables.

    Args:
        settings: Complete QA generation settings.

    Returns:
        Configured TestsetGenerator ready to generate QA pairs.

    Raises:
        ValueError: If required API keys are missing or configuration is invalid.
        ImportError: If ragas, litellm, or instructor packages are not installed.
    """
    logger.info("creating_testset_generator", llm_provider=settings.llm_provider)

    generator_config = settings.to_generator_config()
    llm = create_ragas_llm(generator_config.llm)
    embeddings = create_ragas_embeddings(generator_config.embedding)

    generator = TestsetGenerator(
        llm=llm,
        embedding_model=embeddings,  # type: ignore[arg-type]  # LiteLLMEmbeddings is BaseRagasEmbedding; TestsetGenerator is typed as BaseRagasEmbeddings but accepts both at runtime
    )

    logger.info("testset_generator_created", llm_model=generator_config.llm.model, embedding_model=generator_config.embedding.model)

    return generator
