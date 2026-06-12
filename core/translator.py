"""
translator.py
Core translation logic for Gemini and OpenRouter API providers.
Each provider is a separate class implementing a common interface.
"""

import os
import json
import urllib.request
import urllib.error
from typing import Optional


# ── Language registry ────────────────────────────────────────────────────────

LANGUAGES = {
    "Auto-detect": "auto",
    "Afrikaans": "af",
    "Arabic": "ar",
    "Bengali": "bn",
    "Bulgarian": "bg",
    "Catalan": "ca",
    "Chinese (Simplified)": "zh",
    "Chinese (Traditional)": "zh-TW",
    "Croatian": "hr",
    "Czech": "cs",
    "Danish": "da",
    "Dutch": "nl",
    "English": "en",
    "Estonian": "et",
    "Finnish": "fi",
    "French": "fr",
    "German": "de",
    "Greek": "el",
    "Gujarati": "gu",
    "Hebrew": "he",
    "Hindi": "hi",
    "Hungarian": "hu",
    "Indonesian": "id",
    "Italian": "it",
    "Japanese": "ja",
    "Kannada": "kn",
    "Korean": "ko",
    "Latvian": "lv",
    "Lithuanian": "lt",
    "Malay": "ms",
    "Malayalam": "ml",
    "Marathi": "mr",
    "Norwegian": "no",
    "Persian": "fa",
    "Polish": "pl",
    "Portuguese": "pt",
    "Punjabi": "pa",
    "Romanian": "ro",
    "Russian": "ru",
    "Serbian": "sr",
    "Slovak": "sk",
    "Slovenian": "sl",
    "Spanish": "es",
    "Swahili": "sw",
    "Swedish": "sv",
    "Tamil": "ta",
    "Telugu": "te",
    "Thai": "th",
    "Turkish": "tr",
    "Ukrainian": "uk",
    "Urdu": "ur",
    "Vietnamese": "vi",
    "Welsh": "cy",
}

LANGUAGE_NAMES = list(LANGUAGES.keys())


def build_prompt(text: str, source_lang: str, target_lang: str) -> str:
    """Build a concise, unambiguous translation prompt."""
    if source_lang == "Auto-detect":
        src_clause = "the source language (auto-detect it)"
    else:
        src_clause = source_lang

    return (
        f"Translate the following text from {src_clause} to {target_lang}. "
        "Output ONLY the translated text — no explanations, no quotation marks, "
        "no additional commentary.\n\n"
        f"{text}"
    )


# ── Base class ────────────────────────────────────────────────────────────────

class TranslationError(Exception):
    """Raised when a translation attempt fails for any reason."""


class BaseTranslator:
    """Abstract interface every provider must implement."""

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        raise NotImplementedError

    @staticmethod
    def _http_post(url: str, headers: dict, payload: dict) -> dict:
        """Minimal JSON HTTP POST using only the stdlib."""
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise TranslationError(
                f"HTTP {exc.code} – {exc.reason}\n{body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise TranslationError(
                f"Network error: {exc.reason}"
            ) from exc


# ── Gemini provider ───────────────────────────────────────────────────────────

GEMINI_MODELS = {
    # Free Tier - Ultra-Fast & High-Volume Models
    "gemini-3.1-flash-lite": "Gemini 3.1 Flash-Lite (Speed Optimized - Free Tier)",
    "gemini-3.5-flash": "Gemini 3.5 Flash (Agentic & Coding - Free Tier)",
    
    # Premium / Advanced Reasoning Tier
    "gemini-3.1-pro-preview": "Gemini 3.1 Pro Preview (Deep Reasoning - Premium Tier)",
    "gemini-2.5-pro": "Gemini 2.5 Pro (Stable Workhorse - Premium Tier)",
    
    # Specialized / Experimental Preview
    "gemini-3-deep-think": "Gemini 3 Deep Think (Complex Logic - Preview Tier)",
}

GEMINI_MODEL_NAMES = list(GEMINI_MODELS.keys())


class GeminiTranslator(BaseTranslator):
    """
    Uses the Google Gemini generateContent REST endpoint.
    The model can be chosen by the user; defaults to gemini-2.0-flash-lite.
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.0-flash-lite",
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model = model
        if not self.api_key:
            raise TranslationError(
                "No Gemini API key found.\n"
                "Set it in Settings or via the GEMINI_API_KEY environment variable."
            )

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        prompt = build_prompt(text, source_lang, target_lang)
        url = self.BASE_URL.format(model=self.model) + f"?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,   # Low temp → more deterministic translations
                "maxOutputTokens": 4096,
            },
        }
        result = self._http_post(url, {"Content-Type": "application/json"}, payload)

        try:
            return result["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError) as exc:
            raise TranslationError(
                f"Unexpected Gemini response format:\n{result}"
            ) from exc


# ── OpenRouter provider ───────────────────────────────────────────────────────

OPENROUTER_MODELS = {
    # Free Tier & Budget Models
    "openrouter/free": "OpenRouter Free (Auto-Routing - Free Tier)",
    "deepseek/deepseek-v4-flash": "DeepSeek V4 Flash (Ultra-Fast)",
    
    # Advanced Reasoning & Coding
    "deepseek/deepseek-v4-pro": "DeepSeek V4 Pro (Deep Reasoning & Coding)",
    "meta-llama/llama-4-maverick": "Llama 4 Maverick (Next-Gen Intelligence)",
    
    # Specialized / Mobile Optimized
    "xiaomi/mimo-v2.5": "Xiaomi Mimo v2.5 (On-Device & Efficient)",
}

OPENROUTER_MODEL_NAMES = list(OPENROUTER_MODELS.keys())


class OpenRouterTranslator(BaseTranslator):
    """
    Uses the OpenRouter unified LLM API (OpenAI-compatible endpoint).
    Allows the user to pick from several models.
    """

    API_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "meta-llama/llama-3.3-70b-instruct",
    ):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.model = model
        if not self.api_key:
            raise TranslationError(
                "No OpenRouter API key found.\n"
                "Set it in Settings or via the OPENROUTER_API_KEY environment variable."
            )

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        prompt = build_prompt(text, source_lang, target_lang)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://ai-translator-app",
            "X-Title": "AI Translator",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 8192,
        }
        result = self._http_post(self.API_URL, headers, payload)

        try:
            return result["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as exc:
            raise TranslationError(
                f"Unexpected OpenRouter response format:\n{result}"
            ) from exc
