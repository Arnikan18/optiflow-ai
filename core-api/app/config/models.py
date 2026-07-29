"""Supported LLM providers and stable text models.

Keep this catalog server-owned so API validation, runtime selection, and the
frontend dropdown all use the same model identifiers.
"""

from typing import Final


SETTINGS_SCHEMA_VERSION: Final[int] = 1

SUPPORTED_MODELS: Final[dict[str, tuple[str, ...]]] = {
    "gemini": (
        "gemini-3.5-flash",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.5-pro",
    ),
    "groq": (
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
    ),
}

DEFAULT_MODELS: Final[dict[str, str]] = {
    "gemini": "gemini-2.5-flash",
    "groq": "llama-3.1-8b-instant",
}

PROVIDER_LABELS: Final[dict[str, str]] = {
    "gemini": "Google Gemini",
    "groq": "GroqCloud",
}


def normalize_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized not in SUPPORTED_MODELS:
        raise ValueError(f"Unsupported LLM provider: {provider}")
    return normalized


def validate_model(provider: str, model: str) -> str:
    normalized_provider = normalize_provider(provider)
    normalized_model = model.strip()
    if normalized_model not in SUPPORTED_MODELS[normalized_provider]:
        raise ValueError(
            f"Unsupported model '{model}' for provider '{normalized_provider}'"
        )
    return normalized_model
