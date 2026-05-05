"""Constants for the LLM provider layer."""

# litellm model name prefixes by provider.
# OpenAI model names are used bare; Gemini requires the "gemini/" prefix.
LITELLM_MODEL_PREFIX: dict[str, str] = {
    "openai": "",
    "google": "gemini/",
    "gemini": "gemini/",
}

# Required environment variable per provider for API key validation.
PROVIDER_ENV_VAR: dict[str, tuple[str, ...]] = {
    "openai": ("OPENAI_API_KEY",),
    "google": ("GOOGLE_API_KEY",),
    "gemini": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
}

# Valid chat model name prefixes per provider.
# Used to catch typos and config errors at startup. New model families may require updates here.
VALID_CHAT_MODEL_PREFIXES: dict[str, list[str]] = {
    "openai": ["gpt-", "o1-", "o3-"],
    "google": ["gemini-"],
    "gemini": ["gemini-"],
}

# Valid embedding model name prefixes per provider.
# Kept separate from chat prefixes so cross-wiring (e.g. using a chat model as an embedder)
# is caught at startup rather than at first inference call.
VALID_EMBEDDING_MODEL_PREFIXES: dict[str, list[str]] = {
    "openai": ["text-embedding-"],
    "google": ["text-embedding-", "embedding-", "gemini-embedding-"],
    "gemini": ["text-embedding-", "embedding-", "gemini-embedding-"],
}
