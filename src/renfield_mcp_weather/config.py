"""
Configuration module — Load API URLs and other settings.

API URLs are stored in a JSON file and can be overridden via:
1. Environment variable OPEN_METEO_CONFIG_FILE pointing to a custom JSON file
2. Individual environment variables (e.g., OPEN_METEO_API_URL_FORECAST)

This allows changing API endpoints without rebuilding the code.
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("renfield-mcp-weather")

# Built-in config directory (inside package)
BUILTIN_CONFIG_DIR = Path(__file__).parent / "config"

# Custom config file (from environment variable)
CUSTOM_CONFIG_FILE = os.environ.get("OPEN_METEO_CONFIG_FILE")

# Cache for loaded config
_config_cache: dict | None = None


def _load_config_file(filepath: Path) -> dict | None:
    """Load a config JSON file."""
    try:
        with open(filepath, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to load config file {filepath}: {e}")
        return None


def _load_api_urls() -> dict[str, str]:
    """Load API URLs from config file."""
    urls = {}

    # Load built-in config
    builtin_file = BUILTIN_CONFIG_DIR / "api_urls.json"
    if builtin_file.exists():
        data = _load_config_file(builtin_file)
        if data:
            urls.update(data)
            logger.debug(f"Loaded {len(data)} API URLs from built-in config")

    # Load custom config (overrides built-in)
    if CUSTOM_CONFIG_FILE:
        custom_file = Path(CUSTOM_CONFIG_FILE)
        if custom_file.exists():
            data = _load_config_file(custom_file)
            if data:
                urls.update(data)
                logger.debug(f"Loaded custom config from {custom_file}")
        else:
            logger.warning(f"Custom config file not found: {CUSTOM_CONFIG_FILE}")

    # Apply individual environment variable overrides
    # Format: OPEN_METEO_API_URL_<KEY> (e.g., OPEN_METEO_API_URL_FORECAST)
    for key in list(urls.keys()):
        env_var = f"OPEN_METEO_API_URL_{key.upper()}"
        env_value = os.environ.get(env_var)
        if env_value:
            urls[key] = env_value
            logger.debug(f"Override {key} from {env_var}")

    # Legacy support: OPEN_METEO_API_URL overrides the base for main APIs
    legacy_base = os.environ.get("OPEN_METEO_API_URL")
    if legacy_base:
        # Override URLs that use the main API base
        main_api_keys = ["forecast", "elevation", "dwd_icon", "gfs", "meteofrance",
                        "ecmwf", "jma", "metno", "gem"]
        for key in main_api_keys:
            if key in urls:
                # Extract the path from the original URL
                original = urls[key]
                path = original.split("/v1/")[-1] if "/v1/" in original else ""
                urls[key] = f"{legacy_base.rstrip('/')}/v1/{path}"
        logger.debug(f"Applied legacy OPEN_METEO_API_URL override: {legacy_base}")

    return urls


def get_config() -> dict:
    """Get the full configuration (cached)."""
    global _config_cache
    if _config_cache is None:
        _config_cache = {
            "api_urls": _load_api_urls(),
        }
    return _config_cache


def reload_config() -> dict:
    """Force reload of configuration."""
    global _config_cache
    _config_cache = None
    return get_config()


def get_api_urls() -> dict[str, str]:
    """Get API URLs dictionary."""
    return get_config()["api_urls"]


def get_api_url(key: str) -> str:
    """Get a specific API URL by key."""
    urls = get_api_urls()
    if key not in urls:
        raise KeyError(f"Unknown API URL key: {key}")
    return urls[key]
