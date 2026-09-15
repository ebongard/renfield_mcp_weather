"""Tests for MCP server tools."""

import pytest
import respx
from httpx import Response

from renfield_mcp_weather.server import (
    get_weather,
    get_weather_archive,
    get_air_quality,
    get_elevation,
    geocode_location,
)
from renfield_mcp_weather.locales import (
    get_weather_description,
    get_locales,
    get_supported_languages,
)


# === Weather Code Tests ===


def test_weather_code_translation():
    """Test WMO weather code translation in German (default)."""
    assert get_weather_description(0) == "Klar"
    assert get_weather_description(3) == "Bedeckt"
    assert get_weather_description(61) == "Leichter Regen"
    assert get_weather_description(95) == "Gewitter"
    assert get_weather_description(999) == "Unbekannt (999)"


def test_weather_code_translation_english():
    """Test WMO weather code translation in English."""
    assert get_weather_description(0, "en") == "Clear sky"
    assert get_weather_description(3, "en") == "Overcast"
    assert get_weather_description(61, "en") == "Slight rain"
    assert get_weather_description(95, "en") == "Thunderstorm"
    assert get_weather_description(999, "en") == "Unknown (999)"


def test_all_weather_codes_have_descriptions():
    """Verify all standard WMO codes are covered in all loaded languages."""
    standard_codes = [0, 1, 2, 3, 45, 48, 51, 53, 55, 61, 63, 65, 71, 73, 75, 80, 81, 82, 95, 96, 99]
    locales = get_locales()
    assert "de" in locales, "German locale should be available"
    assert "en" in locales, "English locale should be available"
    for lang, locale_data in locales.items():
        weather_codes = locale_data.get("weather_codes", {})
        for code in standard_codes:
            assert str(code) in weather_codes, f"Code {code} missing in {lang}"


# === Geocode Location Tool Tests ===


@pytest.mark.asyncio
async def test_geocode_location_tool():
    """Test geocode_location tool."""
    with respx.mock:
        respx.get("https://geocoding-api.open-meteo.com/v1/search").mock(
            return_value=Response(200, json={
                "results": [
                    {
                        "latitude": 52.52,
                        "longitude": 13.405,
                        "name": "Berlin",
                        "country": "Germany",
                        "timezone": "Europe/Berlin",
                        "population": 3644826,
                    }
                ]
            })
        )

        result = await geocode_location("Berlin")

        assert "results" in result
        assert len(result["results"]) == 1
        assert result["results"][0]["name"] == "Berlin"
        assert result["query"] == "Berlin"


@pytest.mark.asyncio
async def test_geocode_location_not_found():
    """Test geocode_location tool with no results."""
    with respx.mock:
        respx.get("https://geocoding-api.open-meteo.com/v1/search").mock(
            return_value=Response(200, json={"results": []})
        )

        result = await geocode_location("NonexistentPlace123")

        assert "error" in result


# === Get Weather Tests ===


@pytest.mark.asyncio
async def test_get_weather_success():
    """Test get_weather tool with mock API responses."""
    with respx.mock:
        # Mock geocoding
        respx.get("https://geocoding-api.open-meteo.com/v1/search").mock(
            return_value=Response(200, json={
                "results": [{
                    "latitude": 52.52,
                    "longitude": 13.405,
                    "name": "Berlin",
                    "country": "Germany",
                    "timezone": "Europe/Berlin",
                    "population": 3644826,
                }]
            })
        )

        # Mock weather API
        respx.get("https://api.open-meteo.com/v1/forecast").mock(
            return_value=Response(200, json={
                "current": {
                    "temperature_2m": 8.5,
                    "weather_code": 3,
                    "wind_speed_10m": 12.0,
                    "wind_direction_10m": 180,
                    "relative_humidity_2m": 75,
                    "apparent_temperature": 6.2,
                    "precipitation": 0.0,
                    "cloud_cover": 100,
                },
                "daily": {
                    "time": ["2024-02-06", "2024-02-07"],
                    "temperature_2m_max": [10.0, 12.0],
                    "temperature_2m_min": [4.0, 5.0],
                    "weather_code": [3, 61],
                    "precipitation_sum": [0.0, 2.5],
                    "precipitation_probability_max": [10, 80],
                    "wind_speed_10m_max": [15.0, 20.0],
                    "sunrise": ["2024-02-06T07:30", "2024-02-07T07:28"],
                    "sunset": ["2024-02-06T17:15", "2024-02-07T17:17"],
                }
            })
        )

        result = await get_weather("Berlin")

        assert "location" in result
        assert result["location"]["name"] == "Berlin"
        assert result["location"]["country"] == "Germany"

        assert "current" in result
        assert result["current"]["temperature"] == 8.5
        assert result["current"]["weather_code"] == 3
        assert result["current"]["weather_description"] == "Bedeckt"

        assert "daily" in result
        assert len(result["daily"]) == 2
        assert result["daily"][0]["date"] == "2024-02-06"
        assert result["daily"][0]["temp_max"] == 10.0


@pytest.mark.asyncio
async def test_get_weather_location_not_found():
    """Test get_weather with invalid location."""
    with respx.mock:
        respx.get("https://geocoding-api.open-meteo.com/v1/search").mock(
            return_value=Response(200, json={"results": []})
        )

        result = await get_weather("NonexistentPlace123")

        assert "error" in result
        # Default language is German
        assert "Ort nicht gefunden" in result["error"]


@pytest.mark.asyncio
async def test_get_weather_location_not_found_english():
    """Test get_weather with invalid location in English."""
    with respx.mock:
        respx.get("https://geocoding-api.open-meteo.com/v1/search").mock(
            return_value=Response(200, json={"results": []})
        )

        result = await get_weather("NonexistentPlace123", language="en")

        assert "error" in result
        assert "Location not found" in result["error"]


# === Get Weather Archive Tests ===


@pytest.mark.asyncio
async def test_get_weather_archive_success():
    """Test get_weather_archive tool."""
    with respx.mock:
        # Mock geocoding
        respx.get("https://geocoding-api.open-meteo.com/v1/search").mock(
            return_value=Response(200, json={
                "results": [{
                    "latitude": 48.137,
                    "longitude": 11.575,
                    "name": "München",
                    "country": "Germany",
                    "timezone": "Europe/Berlin",
                }]
            })
        )

        # Mock archive API
        respx.get("https://archive-api.open-meteo.com/v1/archive").mock(
            return_value=Response(200, json={
                "daily": {
                    "time": ["2024-01-01", "2024-01-02"],
                    "temperature_2m_max": [5.0, 6.0],
                    "temperature_2m_min": [-2.0, -1.0],
                    "precipitation_sum": [0.0, 1.0],
                    "weather_code": [0, 61],
                }
            })
        )

        result = await get_weather_archive("München", "2024-01-01", "2024-01-02")

        assert "location" in result
        assert result["location"]["name"] == "München"
        assert "daily" in result
        assert len(result["daily"]) == 2


# === Get Air Quality Tests ===


@pytest.mark.asyncio
async def test_get_air_quality_success():
    """Test get_air_quality tool."""
    with respx.mock:
        # Mock geocoding
        respx.get("https://geocoding-api.open-meteo.com/v1/search").mock(
            return_value=Response(200, json={
                "results": [{
                    "latitude": 48.78,
                    "longitude": 9.18,
                    "name": "Stuttgart",
                    "country": "Germany",
                    "timezone": "Europe/Berlin",
                }]
            })
        )

        # Mock air quality API
        respx.get("https://air-quality-api.open-meteo.com/v1/air-quality").mock(
            return_value=Response(200, json={
                "current": {
                    "european_aqi": 45,
                    "pm10": 20.5,
                    "pm2_5": 12.3,
                    "ozone": 55.0,
                    "nitrogen_dioxide": 18.0,
                },
                "hourly": {
                    "time": ["2024-02-06T00:00"],
                    "pm10": [20.5],
                    "pm2_5": [12.3],
                    "european_aqi": [45],
                }
            })
        )

        result = await get_air_quality("Stuttgart")

        assert "location" in result
        assert "current" in result
        assert result["current"]["pm2_5"] == 12.3


# === Get Elevation Tests ===


@pytest.mark.asyncio
async def test_get_elevation_success():
    """Test get_elevation tool."""
    with respx.mock:
        # Mock geocoding
        respx.get("https://geocoding-api.open-meteo.com/v1/search").mock(
            return_value=Response(200, json={
                "results": [{
                    "latitude": 47.37,
                    "longitude": 8.55,
                    "name": "Zürich",
                    "country": "Switzerland",
                    "timezone": "Europe/Zurich",
                }]
            })
        )

        # Mock elevation API
        respx.get("https://api.open-meteo.com/v1/elevation").mock(
            return_value=Response(200, json={
                "elevation": [408.0]
            })
        )

        result = await get_elevation("Zürich")

        assert "location" in result
        assert result["location"]["name"] == "Zürich"
        assert result["elevation_m"] == 408.0


# === Error Handling Tests ===


@pytest.mark.asyncio
async def test_api_timeout_handling():
    """Test handling of API timeout."""
    import httpx

    with respx.mock:
        # Mock geocoding
        respx.get("https://geocoding-api.open-meteo.com/v1/search").mock(
            return_value=Response(200, json={
                "results": [{
                    "latitude": 52.52,
                    "longitude": 13.405,
                    "name": "Berlin",
                    "country": "Germany",
                    "timezone": "Europe/Berlin",
                }]
            })
        )

        # Mock weather API with timeout
        respx.get("https://api.open-meteo.com/v1/forecast").mock(
            side_effect=httpx.TimeoutException("Connection timed out")
        )

        result = await get_weather("Berlin")

        assert "error" in result
        assert "timeout" in result["error"].lower()


@pytest.mark.asyncio
async def test_api_error_handling():
    """Test handling of API HTTP errors."""
    with respx.mock:
        # Mock geocoding
        respx.get("https://geocoding-api.open-meteo.com/v1/search").mock(
            return_value=Response(200, json={
                "results": [{
                    "latitude": 52.52,
                    "longitude": 13.405,
                    "name": "Berlin",
                    "country": "Germany",
                    "timezone": "Europe/Berlin",
                }]
            })
        )

        # Mock weather API with error
        respx.get("https://api.open-meteo.com/v1/forecast").mock(
            return_value=Response(500, json={"error": "Internal Server Error"})
        )

        result = await get_weather("Berlin")

        assert "error" in result
        assert "500" in result["error"]


# === Upstream throttle (HTTP 429) ===
#
# A throttled Open-Meteo used to come back as {"error": "Weather API error: 429"} —
# prose Renfield's MCP rate-limit classifier deliberately does not read (a bare
# "429" may be an invoice number or a postcode). The contract is structured
# instead: "status": 429 plus "retry_after" in seconds when the upstream sent one.

_BERLIN = {
    "results": [{
        "latitude": 52.52,
        "longitude": 13.405,
        "name": "Berlin",
        "country": "Germany",
        "timezone": "Europe/Berlin",
    }]
}


def _mock_forecast(response):
    respx.get("https://geocoding-api.open-meteo.com/v1/search").mock(
        return_value=Response(200, json=_BERLIN)
    )
    respx.get("https://api.open-meteo.com/v1/forecast").mock(return_value=response)


@pytest.mark.asyncio
async def test_api_throttle_is_a_structured_error_with_retry_after():
    with respx.mock:
        _mock_forecast(Response(429, headers={"Retry-After": "30"}))
        result = await get_weather("Berlin")

    assert result["status"] == 429
    assert result["retry_after"] == 30
    assert "429" in result["error"]


@pytest.mark.asyncio
async def test_api_throttle_without_retry_after_carries_no_guess():
    with respx.mock:
        _mock_forecast(Response(429))
        result = await get_weather("Berlin")

    assert result["status"] == 429
    assert "retry_after" not in result


@pytest.mark.asyncio
async def test_api_throttle_http_date_retry_after_is_not_guessed():
    # The HTTP-date form would need clock arithmetic across skew; omitted, not guessed.
    with respx.mock:
        _mock_forecast(Response(429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}))
        result = await get_weather("Berlin")

    assert result["status"] == 429
    assert "retry_after" not in result


@pytest.mark.asyncio
async def test_other_http_errors_keep_their_envelope():
    with respx.mock:
        _mock_forecast(Response(500, json={"error": "Internal Server Error"}))
        result = await get_weather("Berlin")

    assert result == {"error": "Weather API error: 500"}


@pytest.mark.asyncio
async def test_throttle_reaches_the_mcp_wire_as_structured_json():
    """What Renfield's client actually reads is the tool's TEXT content, parsed as JSON."""
    import json

    from renfield_mcp_weather.server import mcp

    with respx.mock:
        _mock_forecast(Response(429, headers={"Retry-After": "12"}))
        result = await mcp.call_tool("get_weather", {"location": "Berlin"})

    # FastMCP returns (content, structured) or just the content, by output schema.
    content = result[0] if isinstance(result, tuple) else result
    payload = json.loads(content[0].text)
    assert payload["status"] == 429
    assert payload["retry_after"] == 12
