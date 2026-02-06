"""
Localization module — Load language files for weather descriptions.

Languages are stored as JSON files in the locales directory.
Additional languages can be added by placing JSON files in:
1. The package's locales/ directory (built-in)
2. A custom directory specified via OPEN_METEO_LOCALES_DIR environment variable

JSON file format:
{
  "language_name": "English",
  "weather_codes": {
    "0": "Clear sky",
    "3": "Overcast",
    ...
  },
  "errors": {
    "location_not_found": "Location not found: {location}",
    "location_suggestion": "Try a larger city nearby",
    "unknown_weather": "Unknown ({code})"
  }
}
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("renfield-mcp-weather")

# Built-in locales directory (inside package)
BUILTIN_LOCALES_DIR = Path(__file__).parent / "locales"

# Custom locales directory (from environment variable)
CUSTOM_LOCALES_DIR = os.environ.get("OPEN_METEO_LOCALES_DIR")

# Default language
DEFAULT_LANGUAGE = os.environ.get("OPEN_METEO_LANGUAGE", "de")

# Cache for loaded locales
_locales_cache: dict[str, dict] = {}


def _load_locale_file(filepath: Path) -> dict | None:
    """Load a single locale JSON file."""
    try:
        with open(filepath, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to load locale file {filepath}: {e}")
        return None


def _discover_locales() -> dict[str, dict]:
    """Discover and load all available locale files."""
    locales = {}

    # Load built-in locales
    if BUILTIN_LOCALES_DIR.exists():
        for filepath in BUILTIN_LOCALES_DIR.glob("*.json"):
            lang_code = filepath.stem
            locale_data = _load_locale_file(filepath)
            if locale_data:
                locales[lang_code] = locale_data
                logger.debug(f"Loaded built-in locale: {lang_code}")

    # Load custom locales (can override built-in)
    if CUSTOM_LOCALES_DIR:
        custom_dir = Path(CUSTOM_LOCALES_DIR)
        if custom_dir.exists():
            for filepath in custom_dir.glob("*.json"):
                lang_code = filepath.stem
                locale_data = _load_locale_file(filepath)
                if locale_data:
                    locales[lang_code] = locale_data
                    logger.debug(f"Loaded custom locale: {lang_code} from {filepath}")
        else:
            logger.warning(f"Custom locales directory not found: {CUSTOM_LOCALES_DIR}")

    return locales


def get_locales() -> dict[str, dict]:
    """Get all loaded locales (cached)."""
    global _locales_cache
    if not _locales_cache:
        _locales_cache = _discover_locales()
    return _locales_cache


def reload_locales() -> dict[str, dict]:
    """Force reload of all locales."""
    global _locales_cache
    _locales_cache = _discover_locales()
    return _locales_cache


def get_supported_languages() -> set[str]:
    """Get set of supported language codes."""
    return set(get_locales().keys())


def get_locale(language: str) -> dict:
    """Get locale data for a language, falling back to default if not found."""
    locales = get_locales()
    if language in locales:
        return locales[language]
    if DEFAULT_LANGUAGE in locales:
        return locales[DEFAULT_LANGUAGE]
    # Ultimate fallback: return first available locale
    if locales:
        return next(iter(locales.values()))
    # No locales available - return empty structure
    return {"weather_codes": {}, "errors": {}}


def get_weather_description(code: int, language: str = DEFAULT_LANGUAGE) -> str:
    """Translate WMO weather code to description in specified language."""
    locale = get_locale(language)
    weather_codes = locale.get("weather_codes", {})

    # JSON keys are strings, so convert code to string
    description = weather_codes.get(str(code))
    if description:
        return description

    # Return unknown message
    errors = locale.get("errors", {})
    unknown_template = errors.get("unknown_weather", "Unknown ({code})")
    return unknown_template.format(code=code)


def get_error_message(error_key: str, language: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    """Get localized error message."""
    locale = get_locale(language)
    errors = locale.get("errors", {})
    template = errors.get(error_key, error_key)
    try:
        return template.format(**kwargs)
    except KeyError:
        return template
