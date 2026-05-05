"""RAGAS adapter: wires LLMManager / EmbeddingManager into RAGAS-compatible types."""

from __future__ import annotations

from typing import Any

import litellm
import structlog
from ragas.embeddings import LiteLLMEmbeddings
from ragas.llms import llm_factory

from qa_generation.llm.manager import EmbeddingManager, LLMManager

logger = structlog.get_logger(__name__)


class RagasLLMManager:
    """Adapts LLMManager to produce a RAGAS-compatible InstructorBaseRagasLLM.

    Uses RAGAS's llm_factory with the litellm provider and an instructor async
    client so that structured output parsing works correctly with RAGAS 0.4.x.
    """

    def __init__(self, llm_manager: LLMManager) -> None:
        """Initialize with a pre-validated LLMManager.

        Args:
            llm_manager: Framework-agnostic manager providing model name and params.
        """
        self._manager = llm_manager
        self._llm: Any | None = None

    def get_llm(self) -> Any:  # InstructorBaseRagasLLM (not publicly typed by ragas)
        """Return (or lazily create) the RAGAS InstructorBaseRagasLLM instance."""
        if self._llm is None:
            model_name = self._manager.get_model_name()
            params = self._manager.get_llm_params()
            logger.info("building_ragas_llm", model=model_name)
            # Pass litellm.acompletion directly — RAGAS auto-detects it as the litellm adapter
            # and wraps it in LiteLLMStructuredLLM internally. Pre-wrapping with instructor
            # breaks the adapter detection (AsyncInstructor is not callable by RAGAS).
            self._llm = llm_factory(model=model_name, provider="litellm", client=litellm.acompletion, **params)
        return self._llm


class RagasEmbeddingManager:
    """Adapts EmbeddingManager to produce a RAGAS-compatible LiteLLMEmbeddings instance."""

    def __init__(self, embedding_manager: EmbeddingManager) -> None:
        """Initialize with a pre-validated EmbeddingManager.

        Args:
            embedding_manager: Framework-agnostic manager providing the model name.
        """
        self._manager = embedding_manager
        self._embeddings: LiteLLMEmbeddings | None = None

    def get_embeddings(self) -> LiteLLMEmbeddings:
        """Return (or lazily create) the RAGAS LiteLLMEmbeddings instance."""
        if self._embeddings is None:
            model_name = self._manager.get_model_name()
            logger.info("building_ragas_embeddings", model=model_name)
            self._embeddings = LiteLLMEmbeddings(model=model_name)
        return self._embeddings
