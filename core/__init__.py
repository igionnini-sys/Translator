"""AI Translator – core package."""
from .translator import (
    GeminiTranslator,
    OpenRouterTranslator,
    TranslationError,
    LANGUAGES,
    LANGUAGE_NAMES,
    GEMINI_MODELS,
    GEMINI_MODEL_NAMES,
    OPENROUTER_MODELS,
    OPENROUTER_MODEL_NAMES,
)
from .settings import load as load_settings, save as save_settings

__all__ = [
    "GeminiTranslator",
    "OpenRouterTranslator",
    "TranslationError",
    "LANGUAGES",
    "LANGUAGE_NAMES",
    "GEMINI_MODELS",
    "GEMINI_MODEL_NAMES",
    "OPENROUTER_MODELS",
    "OPENROUTER_MODEL_NAMES",
    "load_settings",
    "save_settings",
]
