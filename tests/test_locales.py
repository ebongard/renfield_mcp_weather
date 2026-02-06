"""Tests for locales module."""

import json
import tempfile
from pathlib import Path

import pytest

from renfield_mcp_weather.locales import (
    DEFAULT_LANGUAGE,
    get_error_message,
    get_locale,
    get_locales,
    get_supported_languages,
    get_weather_description,
    reload_locales,
)


def test_default_language():
    """Test default language is German."""
    assert DEFAULT_LANGUAGE == "de"


def test_supported_languages():
    """Test that German and English are supported."""
    languages = get_supported_languages()
    assert "de" in languages
    assert "en" in languages


def test_get_locales_returns_dict():
    """Test that get_locales returns a dictionary."""
    locales = get_locales()
    assert isinstance(locales, dict)
    assert len(locales) >= 2  # At least de and en


def test_locale_structure():
    """Test that locales have the expected structure."""
    locales = get_locales()
    for lang, locale_data in locales.items():
        assert "weather_codes" in locale_data, f"Missing weather_codes in {lang}"
        assert "errors" in locale_data, f"Missing errors in {lang}"
        assert isinstance(locale_data["weather_codes"], dict)
        assert isinstance(locale_data["errors"], dict)


def test_get_weather_description_german():
    """Test weather description in German."""
    assert get_weather_description(0, "de") == "Klar"
    assert get_weather_description(3, "de") == "Bedeckt"
    assert get_weather_description(95, "de") == "Gewitter"


def test_get_weather_description_english():
    """Test weather description in English."""
    assert get_weather_description(0, "en") == "Clear sky"
    assert get_weather_description(3, "en") == "Overcast"
    assert get_weather_description(95, "en") == "Thunderstorm"


def test_get_weather_description_unknown_code():
    """Test weather description for unknown code."""
    result_de = get_weather_description(999, "de")
    assert "999" in result_de
    assert "Unbekannt" in result_de

    result_en = get_weather_description(999, "en")
    assert "999" in result_en
    assert "Unknown" in result_en


def test_get_weather_description_fallback_language():
    """Test that unknown language falls back to default."""
    # Unknown language should fall back to default (German)
    result = get_weather_description(0, "xx")
    assert result == get_weather_description(0, DEFAULT_LANGUAGE)


def test_get_error_message_german():
    """Test error message in German."""
    msg = get_error_message("location_not_found", "de", location="Berlin")
    assert "Berlin" in msg
    assert "nicht gefunden" in msg


def test_get_error_message_english():
    """Test error message in English."""
    msg = get_error_message("location_not_found", "en", location="Berlin")
    assert "Berlin" in msg
    assert "not found" in msg


def test_get_error_message_suggestion():
    """Test suggestion error message."""
    de_suggestion = get_error_message("location_suggestion", "de")
    assert "größere Stadt" in de_suggestion or "genaueren" in de_suggestion

    en_suggestion = get_error_message("location_suggestion", "en")
    assert "larger city" in en_suggestion or "specific" in en_suggestion


def test_get_locale_fallback():
    """Test that get_locale falls back gracefully."""
    # Unknown language should return default locale
    locale = get_locale("nonexistent_language")
    assert "weather_codes" in locale
