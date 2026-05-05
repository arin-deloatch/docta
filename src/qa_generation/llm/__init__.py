"""Framework-agnostic LLM and embedding managers."""

from qa_generation.llm.manager import EmbeddingManager, LLMManager

__all__ = [
    "LLMManager",
    "EmbeddingManager",
]
