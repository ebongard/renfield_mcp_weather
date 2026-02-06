"""Tests for config module."""

import pytest

from renfield_mcp_weather.config import (
    get_api_url,
    get_api_urls,
    get_config,
    reload_config,
)


def test_get_config_returns_dict():
    """Test that get_config returns a dictionary."""
    config = get_config()
    assert isinstance(config, dict)
    assert "api_urls" in config


def test_get_api_urls_returns_dict():
    """Test that get_api_urls returns a dictionary."""
    urls = get_api_urls()
    assert isinstance(urls, dict)
    assert len(urls) > 0


def test_all_required_api_urls_present():
    """Test that all required API URLs are present."""
    urls = get_api_urls()
    required_keys = [
        "forecast", "archive", "air_quality", "marine", "flood",
        "seasonal", "ensemble", "climate", "elevation", "geocoding",
        "dwd_icon", "gfs", "meteofrance", "ecmwf", "jma", "metno", "gem"
    ]
    for key in required_keys:
        assert key in urls, f"Missing API URL: {key}"


def test_get_api_url_returns_string():
    """Test that get_api_url returns a string."""
    url = get_api_url("forecast")
    assert isinstance(url, str)
    assert url.startswith("http")


def test_get_api_url_unknown_key_raises():
    """Test that get_api_url raises for unknown key."""
    with pytest.raises(KeyError, match="Unknown API URL key"):
        get_api_url("nonexistent_api")


def test_api_urls_are_valid_urls():
    """Test that all API URLs are valid HTTP URLs."""
    urls = get_api_urls()
    for key, url in urls.items():
        assert url.startswith("http://") or url.startswith("https://"), \
            f"Invalid URL for {key}: {url}"


def test_reload_config():
    """Test that reload_config returns fresh config."""
    config1 = get_config()
    config2 = reload_config()
    # Both should have the same structure
    assert "api_urls" in config1
    assert "api_urls" in config2
