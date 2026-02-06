"""
Geocoding helper — Resolve location names to coordinates.

Uses the Open-Meteo Geocoding API (free, no key required).
"""

import os

import httpx

GEOCODING_URL = os.environ.get(
    "OPEN_METEO_GEOCODING_URL",
    "https://geocoding-api.open-meteo.com/v1/search"
)
DEFAULT_LANGUAGE = os.environ.get("OPEN_METEO_LANGUAGE", "de")


async def geocode(location: str, language: str = DEFAULT_LANGUAGE) -> dict:
    """
    Resolve location name to coordinates using Open-Meteo Geocoding API.

    Args:
        location: City name, address, or postal code (e.g., "Berlin", "10115")
        language: Language for result names (default: "de")

    Returns:
        {
            "latitude": float,
            "longitude": float,
            "name": str,
            "country": str,
            "timezone": str,
            "population": int | None
        }

    Raises:
        ValueError: If location cannot be resolved
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        # First attempt: direct search
        resp = await client.get(
            GEOCODING_URL,
            params={"name": location, "count": 5, "language": language}
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])

        if not results:
            # Fallback: try with German country code (for villages)
            resp = await client.get(
                GEOCODING_URL,
                params={"name": location, "count": 5, "language": language, "country_code": "DE"}
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])

        if not results:
            raise ValueError(f"Location not found: {location}")

        # Pick result with highest population (most likely the intended city)
        best = max(results, key=lambda r: r.get("population", 0))

        return {
            "latitude": best["latitude"],
            "longitude": best["longitude"],
            "name": best.get("name", location),
            "country": best.get("country", ""),
            "timezone": best.get("timezone", "auto"),
            "population": best.get("population"),
        }
