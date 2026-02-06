"""Tests for geocoding helper."""

import pytest
import respx
from httpx import Response

from renfield_mcp_weather.geocoding import geocode


@pytest.fixture
def mock_geocoding_api():
    """Mock the Open-Meteo geocoding API."""
    with respx.mock:
        yield respx


@pytest.mark.asyncio
async def test_geocode_berlin(mock_geocoding_api):
    """Test geocoding a major city."""
    mock_geocoding_api.get("https://geocoding-api.open-meteo.com/v1/search").mock(
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

    result = await geocode("Berlin")

    assert result["latitude"] == 52.52
    assert result["longitude"] == 13.405
    assert result["name"] == "Berlin"
    assert result["country"] == "Germany"


@pytest.mark.asyncio
async def test_geocode_picks_largest_population(mock_geocoding_api):
    """Test that geocoding picks the city with largest population."""
    mock_geocoding_api.get("https://geocoding-api.open-meteo.com/v1/search").mock(
        return_value=Response(200, json={
            "results": [
                {"latitude": 51.0, "longitude": 6.0, "name": "Frankfurt (Oder)", "population": 58000},
                {"latitude": 50.1, "longitude": 8.7, "name": "Frankfurt am Main", "population": 753056},
            ]
        })
    )

    result = await geocode("Frankfurt")

    assert result["name"] == "Frankfurt am Main"
    assert result["population"] == 753056


@pytest.mark.asyncio
async def test_geocode_not_found(mock_geocoding_api):
    """Test geocoding with no results raises ValueError."""
    mock_geocoding_api.get("https://geocoding-api.open-meteo.com/v1/search").mock(
        return_value=Response(200, json={"results": []})
    )

    with pytest.raises(ValueError, match="Location not found"):
        await geocode("ThisPlaceDoesNotExist12345")


# TODO: Add more tests:
# - test_geocode_village_with_fallback
# - test_geocode_postal_code
# - test_geocode_timeout
# - test_geocode_api_error
