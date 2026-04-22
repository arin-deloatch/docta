"""Factory for creating LangChain LLM and embedding providers for RAGAS.

This module provides factory functions that create LangChain provider instances
wrapped for use with RAGAS TestsetGenerator.

TODO: Migrate to RAGAS llm_factory for better structured output handling and
      to prepare for future LiteLLM integration. Current wrappers are deprecated
      but functional. See: https://docs.ragas.io/en/latest/concepts/llms/
"""

from __future__ import annotations

import os

import structlog
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.testset import TestsetGenerator

from qa_generation.config.settings import QAGenerationSettings
from qa_generation.models.provider_config import EmbeddingConfig, LLMConfig

logger = structlog.get_logger(__name__)


def create_ragas_llm(config: LLMConfig) -> LangchainLLMWrapper:  # type: ignore[valid-type]  # LangchainLLMWrapper is a variable, not a type alias
    """Create a RAGAS LLM instance using LangChain providers.

    Currently supported providers: OpenAI, Google/Gemini

    API keys must be set in environment variables before calling this function.
    Use QAGenerationSettings.setup_environment() to configure environment.

    Args:
        config: LLM configuration (provider, model, temperature, etc.)

    Returns:
        RAGAS-compatible LLM instance (wrapped LangChain chat model)

    Raises:
        ValueError: If provider is not supported or API key is missing
        ImportError: If required LangChain packages are not installed
    """
    provider_lower = config.provider.lower()

    logger.info(
        "creating_ragas_llm",
        provider=config.provider,
        model=config.model,
        temperature=config.temperature,
    )

    if provider_lower in ("gemini", "google"):
        try:
            from langchain_google_genai import (  # type: ignore[reportMissingImports]  # pylint: disable=import-outside-toplevel
                ChatGoogleGenerativeAI,
            )
        except ImportError as e:
            raise ImportError("langchain-google-genai is required for Google LLM. Install with: uv add langchain-google-genai") from e

        # Verify API key is in environment (set by setup_environment())
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment. Ensure setup_environment() was called before creating LLM.")

        langchain_llm = ChatGoogleGenerativeAI(
            model=config.model,
            temperature=config.temperature,
            max_output_tokens=config.max_tokens,
        )

        return LangchainLLMWrapper(langchain_llm)  # type: ignore[no-any-return]  # RAGAS wrapper returns not fully typed

    if provider_lower == "openai":
        try:
            from langchain_openai import (  # pylint: disable=import-outside-toplevel
                ChatOpenAI,
            )
        except ImportError as e:
            raise ImportError("langchain-openai is required for OpenAI LLM. Install with: uv add langchain-openai") from e

        # Verify API key is in environment (set by setup_environment())
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment. Ensure setup_environment() was called before creating LLM.")

        langchain_llm = ChatOpenAI(  # type: ignore[call-arg,assignment,reportCallIssue]  # max_tokens vs max_completion_tokens naming varies, multiple LLM types
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,  # type: ignore[reportCallIssue]
        )

        return LangchainLLMWrapper(langchain_llm)  # type: ignore[arg-type,no-any-return]  # LangChain wrappers accept multiple chat model types, RAGAS wrapper returns not fully typed

    raise ValueError(f"Unsupported LLM provider: '{config.provider}'. Supported providers: openai, google, gemini")


def create_ragas_embeddings(config: EmbeddingConfig) -> LangchainEmbeddingsWrapper:  # type: ignore[valid-type]  # LangchainEmbeddingsWrapper is a variable, not a type alias
    """Create a RAGAS embeddings instance using LangChain providers.

    Currently supported providers: OpenAI, Google/Gemini

    API keys must be set in environment variables before calling this function.
    Use QAGenerationSettings.setup_environment() to configure environment.

    Args:
        config: Embedding configuration (provider, model)

    Returns:
        RAGAS-compatible embeddings instance (wrapped LangChain embeddings)

    Raises:
        ValueError: If provider is not supported or API key is missing
        ImportError: If required LangChain packages are not installed
    """
    provider_lower = config.provider.lower()

    logger.info(
        "creating_ragas_embeddings",
        provider=provider_lower,
        model=config.model,
    )

    if provider_lower in ("gemini", "google"):
        try:
            from langchain_google_genai import (  # type: ignore[reportMissingImports]  # pylint: disable=import-outside-toplevel
                GoogleGenerativeAIEmbeddings,
            )
        except ImportError as e:
            raise ImportError("langchain-google-genai is required for Google embeddings. Install with: uv add langchain-google-genai") from e

        # Verify API key is in environment (set by setup_environment())
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment. Ensure setup_environment() was called before creating embeddings.")

        langchain_embeddings = GoogleGenerativeAIEmbeddings(model=config.model)

        return LangchainEmbeddingsWrapper(langchain_embeddings)  # type: ignore[no-any-return]  # RAGAS wrapper returns not fully typed

    if provider_lower == "openai":
        try:
            from langchain_openai import (  # pylint: disable=import-outside-toplevel
                OpenAIEmbeddings,
            )
        except ImportError as e:
            raise ImportError("langchain-openai is required for OpenAI embeddings. Install with: uv add langchain-openai") from e

        # Verify API key is in environment (set by setup_environment())
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment. Ensure setup_environment() was called before creating embeddings.")

        langchain_embeddings = OpenAIEmbeddings(model=config.model)  # type: ignore[assignment]  # Multiple embedding provider types

        return LangchainEmbeddingsWrapper(langchain_embeddings)  # type: ignore[arg-type,no-any-return]  # LangChain wrappers accept multiple embedding types, RAGAS wrapper returns not fully typed

    raise ValueError(f"Unsupported embeddings provider: '{provider_lower}'. Supported providers: openai, google, gemini")


def create_testset_generator(settings: QAGenerationSettings) -> TestsetGenerator:
    """Create a configured RAGAS TestsetGenerator.

    This is the main entry point for QA generation. It wires together
    the LLM, embeddings, and generator configuration using LangChain providers.

    IMPORTANT: Call settings.setup_environment() before using this function
    to ensure API keys are set in environment variables.

    Args:
        settings: Complete QA generation settings

    Returns:
        Configured TestsetGenerator ready to generate QA pairs

    Raises:
        ValueError: If required API keys are missing or configuration is invalid
        ImportError: If RAGAS or required LangChain packages are not installed
    """
    logger.info("creating_testset_generator", llm_provider=settings.llm_provider)

    # Create LLM and embeddings (API keys read from environment)
    generator_config = settings.to_generator_config()
    llm = create_ragas_llm(generator_config.llm)
    embeddings = create_ragas_embeddings(generator_config.embedding)

    # Create generator
    generator = TestsetGenerator(llm=llm, embedding_model=embeddings)

    logger.info(
        "testset_generator_created",
        llm_model=generator_config.llm.model,
        embedding_model=generator_config.embedding.model,
    )

    return generator
