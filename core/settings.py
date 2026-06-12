"""
settings.py
Persistent settings storage using a JSON file in the user's home directory.
Handles API keys and last-used preferences.
"""

import json
import os
from pathlib import Path


SETTINGS_PATH = Path.home() / ".ai_translator_settings.json"

_DEFAULTS = {
    "gemini_api_key": "",
    "openrouter_api_key": "",
    "provider": "Gemini",
    "gemini_model": "gemini-2.0-flash-lite",
    "openrouter_model": "meta-llama/llama-3.3-70b-instruct",
    "source_lang": "Auto-detect",
    "target_lang": "English",
    "window_width": 980,
    "window_height": 680,
}


def load() -> dict:
    """Load settings from disk, filling in defaults for missing keys."""
    settings = dict(_DEFAULTS)
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as fh:
                stored = json.load(fh)
            settings.update({k: v for k, v in stored.items() if k in _DEFAULTS})
        except (json.JSONDecodeError, OSError):
            pass  # Corrupt file — fall back to defaults silently

    # Environment variables always win over stored keys
    if os.environ.get("GEMINI_API_KEY"):
        settings["gemini_api_key"] = os.environ["GEMINI_API_KEY"]
    if os.environ.get("OPENROUTER_API_KEY"):
        settings["openrouter_api_key"] = os.environ["OPENROUTER_API_KEY"]

    return settings


def save(settings: dict) -> None:
    """Persist settings to disk. Skips env-only keys to avoid leaking secrets."""
    to_store = {k: v for k, v in settings.items() if k in _DEFAULTS}
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
            json.dump(to_store, fh, indent=2)
    except OSError:
        pass  # Non-critical — settings just won't persist
