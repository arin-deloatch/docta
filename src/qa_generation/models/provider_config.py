"""LLM and embedding provider configuration models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """LLM configuration for QA generation."""

    provider: str = Field(default="openai", description="LLM provider")
    model: str = Field(default="gpt-4o", description="Model name")
    temperature: float = Field(default=0.3, ge=0.0, le=2.0, description="Temperature")
    max_tokens: int | None = Field(default=None, description="Max output tokens")


class EmbeddingConfig(BaseModel):
    """Embedding configuration for RAGAS."""

    provider: str = Field(default="openai", description="Embedding provider")
    model: str = Field(default="text-embedding-3-small", description="Embedding model name")
