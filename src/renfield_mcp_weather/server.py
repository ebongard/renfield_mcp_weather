#!/usr/bin/env python3
"""
renfield-mcp-weather — MCP server for Open-Meteo weather API.

Provides weather tools with location-based API (city names instead of lat/lon).
Geocoding is handled internally and transparently.

See REQUIREMENTS.md for full specification.
"""

import logging
import os
import sys

import httpx
from mcp.server.fastmcp import FastMCP

from .geocoding import geocode
from .locales import (
    DEFAULT_LANGUAGE,
    get_error_message,
    get_supported_languages,
    get_weather_description,
)

# MCP stdio servers must NEVER write to stdout — log to stderr only.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("renfield-mcp-weather")

# === MCP Server ===
mcp = FastMCP("renfield-weather")


# === API Base URLs ===
API_BASE = os.environ.get("OPEN_METEO_API_URL", "https://api.open-meteo.com")

API_URLS = {
    "forecast": f"{API_BASE}/v1/forecast",
    "archive": "https://archive-api.open-meteo.com/v1/archive",
    "air_quality": "https://air-quality-api.open-meteo.com/v1/air-quality",
    "marine": "https://marine-api.open-meteo.com/v1/marine",
    "flood": "https://flood-api.open-meteo.com/v1/flood",
    "seasonal": "https://seasonal-api.open-meteo.com/v1/seasonal",
    "ensemble": "https://ensemble-api.open-meteo.com/v1/ensemble",
    "climate": "https://climate-api.open-meteo.com/v1/climate",
    "elevation": f"{API_BASE}/v1/elevation",
    "dwd_icon": f"{API_BASE}/v1/dwd-icon",
    "gfs": f"{API_BASE}/v1/gfs",
    "meteofrance": f"{API_BASE}/v1/meteofrance",
    "ecmwf": f"{API_BASE}/v1/ecmwf",
    "jma": f"{API_BASE}/v1/jma",
    "metno": f"{API_BASE}/v1/metno",
    "gem": f"{API_BASE}/v1/gem",
}

# HTTP client timeout
HTTP_TIMEOUT = 15.0


# === Helper Functions ===


async def fetch_api(url: str, params: dict) -> dict:
    """Fetch data from Open-Meteo API."""
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def format_location(geo: dict) -> dict:
    """Format location info for response."""
    return {
        "name": geo["name"],
        "country": geo["country"],
        "latitude": geo["latitude"],
        "longitude": geo["longitude"],
    }


def format_current_weather(data: dict, language: str = DEFAULT_LANGUAGE) -> dict | None:
    """Format current weather data."""
    current = data.get("current")
    if not current:
        return None

    result = {}
    if "temperature_2m" in current:
        result["temperature"] = current["temperature_2m"]
    if "weather_code" in current:
        result["weather_code"] = current["weather_code"]
        result["weather_description"] = get_weather_description(current["weather_code"], language)
    if "wind_speed_10m" in current:
        result["wind_speed"] = current["wind_speed_10m"]
    if "wind_direction_10m" in current:
        result["wind_direction"] = current["wind_direction_10m"]
    if "relative_humidity_2m" in current:
        result["humidity"] = current["relative_humidity_2m"]
    if "apparent_temperature" in current:
        result["feels_like"] = current["apparent_temperature"]
    if "precipitation" in current:
        result["precipitation"] = current["precipitation"]
    if "cloud_cover" in current:
        result["cloud_cover"] = current["cloud_cover"]

    return result


def format_daily_forecast(data: dict, language: str = DEFAULT_LANGUAGE) -> list | None:
    """Format daily forecast data."""
    daily = data.get("daily")
    if not daily:
        return None

    time_list = daily.get("time", [])
    result = []

    for i, date in enumerate(time_list):
        day = {"date": date}

        if "temperature_2m_max" in daily:
            day["temp_max"] = daily["temperature_2m_max"][i]
        if "temperature_2m_min" in daily:
            day["temp_min"] = daily["temperature_2m_min"][i]
        if "weather_code" in daily:
            code = daily["weather_code"][i]
            day["weather_code"] = code
            day["weather_description"] = get_weather_description(code, language)
        if "precipitation_sum" in daily:
            day["precipitation"] = daily["precipitation_sum"][i]
        if "precipitation_probability_max" in daily:
            day["precipitation_probability"] = daily["precipitation_probability_max"][i]
        if "wind_speed_10m_max" in daily:
            day["wind_speed_max"] = daily["wind_speed_10m_max"][i]
        if "sunrise" in daily:
            day["sunrise"] = daily["sunrise"][i]
        if "sunset" in daily:
            day["sunset"] = daily["sunset"][i]

        result.append(day)

    return result


def format_hourly_data(data: dict) -> list | None:
    """Format hourly data generically."""
    hourly = data.get("hourly")
    if not hourly:
        return None

    time_list = hourly.get("time", [])
    result = []

    for i, time in enumerate(time_list):
        entry = {"time": time}
        for key, values in hourly.items():
            if key != "time" and isinstance(values, list) and i < len(values):
                entry[key] = values[i]
        result.append(entry)

    return result


async def handle_location_error(location: str, language: str = DEFAULT_LANGUAGE) -> dict:
    """Return error response for location not found."""
    return {
        "error": get_error_message("location_not_found", language, location=location),
        "suggestion": get_error_message("location_suggestion", language),
    }


async def handle_api_error(error: Exception) -> dict:
    """Return error response for API errors."""
    if isinstance(error, httpx.HTTPStatusError):
        return {"error": f"Weather API error: {error.response.status_code}"}
    elif isinstance(error, httpx.TimeoutException):
        return {"error": "Weather API timeout - please try again"}
    else:
        return {"error": f"API error: {str(error)}"}


# === Core Tools ===


@mcp.tool()
async def get_weather(
    location: str,
    days: int = 7,
    hourly: list[str] | None = None,
    daily: list[str] | None = None,
    current: bool = True,
    timezone: str = "auto",
    temperature_unit: str = "celsius",
    wind_speed_unit: str = "kmh",
    precipitation_unit: str = "mm",
    language: str = "de",
) -> dict:
    """
    Get weather forecast for a location.

    Args:
        location: City name or address (e.g., "Berlin", "Kleinenbroich", "10115")
        days: Forecast days (1-16, default: 7)
        hourly: Hourly variables (e.g., ["temperature_2m", "precipitation"])
        daily: Daily variables (e.g., ["temperature_2m_max", "precipitation_sum"])
        current: Include current weather (default: True)
        timezone: Timezone for times (default: "auto" = location's timezone)
        temperature_unit: celsius or fahrenheit
        wind_speed_unit: kmh, ms, mph, or kn
        precipitation_unit: mm or inch
        language: Language for descriptions (de or en, default: de)

    Returns:
        Weather data including current conditions and forecast
    """
    try:
        geo = await geocode(location, language=language)
    except ValueError:
        return await handle_location_error(location, language)

    params = {
        "latitude": geo["latitude"],
        "longitude": geo["longitude"],
        "forecast_days": min(max(days, 1), 16),
        "timezone": timezone if timezone != "auto" else geo["timezone"],
        "temperature_unit": temperature_unit,
        "wind_speed_unit": wind_speed_unit,
        "precipitation_unit": precipitation_unit,
    }

    if current:
        params["current"] = [
            "temperature_2m",
            "relative_humidity_2m",
            "apparent_temperature",
            "weather_code",
            "wind_speed_10m",
            "wind_direction_10m",
            "precipitation",
            "cloud_cover",
        ]

    if daily:
        params["daily"] = daily
    else:
        # Default daily variables
        params["daily"] = [
            "temperature_2m_max",
            "temperature_2m_min",
            "weather_code",
            "precipitation_sum",
            "precipitation_probability_max",
            "wind_speed_10m_max",
            "sunrise",
            "sunset",
        ]

    if hourly:
        params["hourly"] = hourly

    try:
        data = await fetch_api(API_URLS["forecast"], params)
    except Exception as e:
        return await handle_api_error(e)

    result = {"location": format_location(geo)}

    if current:
        result["current"] = format_current_weather(data, language)

    daily_forecast = format_daily_forecast(data, language)
    if daily_forecast:
        result["daily"] = daily_forecast

    if hourly:
        result["hourly"] = format_hourly_data(data)

    return result


@mcp.tool()
async def get_weather_archive(
    location: str,
    start_date: str,
    end_date: str,
    hourly: list[str] | None = None,
    daily: list[str] | None = None,
    timezone: str = "auto",
    temperature_unit: str = "celsius",
    wind_speed_unit: str = "kmh",
    precipitation_unit: str = "mm",
    language: str = "de",
) -> dict:
    """
    Get historical weather data for a location (1940-present).

    Args:
        location: City name or address
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        hourly: Hourly variables to retrieve
        daily: Daily variables to retrieve
        timezone: Timezone for times
        temperature_unit: celsius or fahrenheit
        wind_speed_unit: kmh, ms, mph, or kn
        precipitation_unit: mm or inch
        language: Language for descriptions (de or en, default: de)

    Returns:
        Historical weather data for the specified period
    """
    try:
        geo = await geocode(location, language=language)
    except ValueError:
        return await handle_location_error(location, language)

    params = {
        "latitude": geo["latitude"],
        "longitude": geo["longitude"],
        "start_date": start_date,
        "end_date": end_date,
        "timezone": timezone if timezone != "auto" else geo["timezone"],
        "temperature_unit": temperature_unit,
        "wind_speed_unit": wind_speed_unit,
        "precipitation_unit": precipitation_unit,
    }

    if daily:
        params["daily"] = daily
    else:
        params["daily"] = [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "weather_code",
        ]

    if hourly:
        params["hourly"] = hourly

    try:
        data = await fetch_api(API_URLS["archive"], params)
    except Exception as e:
        return await handle_api_error(e)

    result = {"location": format_location(geo)}

    daily_data = format_daily_forecast(data, language)
    if daily_data:
        result["daily"] = daily_data

    if hourly:
        result["hourly"] = format_hourly_data(data)

    return result


@mcp.tool()
async def get_air_quality(
    location: str,
    hourly: list[str] | None = None,
    current: bool = True,
    forecast_days: int = 5,
    timezone: str = "auto",
    language: str = "de",
) -> dict:
    """
    Get air quality data for a location.

    Args:
        location: City name or address
        hourly: Hourly variables (e.g., ["pm10", "pm2_5", "ozone", "nitrogen_dioxide"])
        current: Include current air quality (default: True)
        forecast_days: Forecast days (1-7, default: 5)
        timezone: Timezone for times
        language: Language for descriptions (de or en, default: de)

    Returns:
        Air quality data including PM2.5, PM10, ozone, etc.
    """
    try:
        geo = await geocode(location, language=language)
    except ValueError:
        return await handle_location_error(location, language)

    params = {
        "latitude": geo["latitude"],
        "longitude": geo["longitude"],
        "forecast_days": min(max(forecast_days, 1), 7),
        "timezone": timezone if timezone != "auto" else geo["timezone"],
    }

    if current:
        params["current"] = [
            "european_aqi",
            "pm10",
            "pm2_5",
            "carbon_monoxide",
            "nitrogen_dioxide",
            "ozone",
        ]

    if hourly:
        params["hourly"] = hourly
    else:
        params["hourly"] = ["pm10", "pm2_5", "european_aqi", "ozone", "nitrogen_dioxide"]

    try:
        data = await fetch_api(API_URLS["air_quality"], params)
    except Exception as e:
        return await handle_api_error(e)

    result = {"location": format_location(geo)}

    if current and "current" in data:
        result["current"] = data["current"]

    hourly_data = format_hourly_data(data)
    if hourly_data:
        result["hourly"] = hourly_data

    return result


@mcp.tool()
async def get_marine_weather(
    location: str,
    hourly: list[str] | None = None,
    daily: list[str] | None = None,
    forecast_days: int = 7,
    timezone: str = "auto",
    length_unit: str = "metric",
    language: str = "de",
) -> dict:
    """
    Get marine weather data (wave height, sea temperature, etc.).

    Args:
        location: Coastal city or coordinates near water
        hourly: Hourly variables (e.g., ["wave_height", "wave_direction"])
        daily: Daily variables
        forecast_days: Forecast days (1-16, default: 7)
        timezone: Timezone for times
        length_unit: metric or imperial
        language: Language for descriptions (de or en, default: de)

    Returns:
        Marine weather data including wave conditions
    """
    try:
        geo = await geocode(location, language=language)
    except ValueError:
        return await handle_location_error(location, language)

    params = {
        "latitude": geo["latitude"],
        "longitude": geo["longitude"],
        "forecast_days": min(max(forecast_days, 1), 16),
        "timezone": timezone if timezone != "auto" else geo["timezone"],
        "length_unit": length_unit,
    }

    if hourly:
        params["hourly"] = hourly
    else:
        params["hourly"] = [
            "wave_height",
            "wave_direction",
            "wave_period",
            "swell_wave_height",
            "ocean_current_velocity",
        ]

    if daily:
        params["daily"] = daily
    else:
        params["daily"] = ["wave_height_max", "wave_direction_dominant", "wave_period_max"]

    try:
        data = await fetch_api(API_URLS["marine"], params)
    except Exception as e:
        return await handle_api_error(e)

    result = {"location": format_location(geo)}

    hourly_data = format_hourly_data(data)
    if hourly_data:
        result["hourly"] = hourly_data

    daily_data = format_daily_forecast(data, language)
    if daily_data:
        result["daily"] = daily_data

    return result


@mcp.tool()
async def get_elevation(location: str, language: str = "de") -> dict:
    """
    Get elevation at a location.

    Args:
        location: City name or address
        language: Language for location names (de or en, default: de)

    Returns:
        Elevation in meters above sea level
    """
    try:
        geo = await geocode(location, language=language)
    except ValueError:
        return await handle_location_error(location, language)

    params = {
        "latitude": geo["latitude"],
        "longitude": geo["longitude"],
    }

    try:
        data = await fetch_api(API_URLS["elevation"], params)
    except Exception as e:
        return await handle_api_error(e)

    elevation = data.get("elevation", [None])[0]

    return {
        "location": format_location(geo),
        "elevation_m": elevation,
    }


@mcp.tool()
async def geocode_location(name: str, count: int = 5, language: str = "de") -> dict:
    """
    Resolve a location name to coordinates.

    Args:
        name: City name, address, or postal code
        count: Maximum number of results (default: 5)
        language: Language for result names (default: "de")

    Returns:
        List of matching locations with coordinates
    """
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": name, "count": count, "language": language},
        )
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results", [])
    if not results:
        return {"error": f"No results for: {name}"}

    return {
        "query": name,
        "results": [
            {
                "name": r.get("name"),
                "country": r.get("country"),
                "latitude": r["latitude"],
                "longitude": r["longitude"],
                "timezone": r.get("timezone"),
                "population": r.get("population"),
            }
            for r in results
        ],
    }


# === Specialized Weather Model Tools ===


async def fetch_model_weather(
    location: str,
    api_url: str,
    model_name: str,
    days: int = 7,
    hourly: list[str] | None = None,
    daily: list[str] | None = None,
    current: bool = True,
    timezone: str = "auto",
    temperature_unit: str = "celsius",
    wind_speed_unit: str = "kmh",
    precipitation_unit: str = "mm",
    language: str = "de",
) -> dict:
    """Generic function to fetch weather from a specific model."""
    try:
        geo = await geocode(location, language=language)
    except ValueError:
        return await handle_location_error(location, language)

    params = {
        "latitude": geo["latitude"],
        "longitude": geo["longitude"],
        "forecast_days": min(max(days, 1), 16),
        "timezone": timezone if timezone != "auto" else geo["timezone"],
        "temperature_unit": temperature_unit,
        "wind_speed_unit": wind_speed_unit,
        "precipitation_unit": precipitation_unit,
    }

    if current:
        params["current"] = [
            "temperature_2m",
            "weather_code",
            "wind_speed_10m",
            "wind_direction_10m",
        ]

    if daily:
        params["daily"] = daily
    else:
        params["daily"] = [
            "temperature_2m_max",
            "temperature_2m_min",
            "weather_code",
            "precipitation_sum",
        ]

    if hourly:
        params["hourly"] = hourly

    try:
        data = await fetch_api(api_url, params)
    except Exception as e:
        return await handle_api_error(e)

    result = {"location": format_location(geo), "model": model_name}

    if current:
        result["current"] = format_current_weather(data, language)

    daily_forecast = format_daily_forecast(data, language)
    if daily_forecast:
        result["daily"] = daily_forecast

    if hourly:
        result["hourly"] = format_hourly_data(data)

    return result


@mcp.tool()
async def get_dwd_icon(
    location: str,
    days: int = 7,
    hourly: list[str] | None = None,
    daily: list[str] | None = None,
    current: bool = True,
    timezone: str = "auto",
    temperature_unit: str = "celsius",
    language: str = "de",
) -> dict:
    """
    Get weather from DWD ICON model (high-resolution, Europe-focused).

    Args:
        location: City name or address (best for Europe/Germany)
        days: Forecast days (1-16, default: 7)
        hourly: Hourly variables
        daily: Daily variables
        current: Include current weather
        timezone: Timezone for times
        temperature_unit: celsius or fahrenheit
        language: Language for descriptions (de or en, default: de)

    Returns:
        Weather forecast from DWD ICON model
    """
    return await fetch_model_weather(
        location, API_URLS["dwd_icon"], "DWD ICON",
        days, hourly, daily, current, timezone, temperature_unit,
        language=language
    )


@mcp.tool()
async def get_gfs(
    location: str,
    days: int = 7,
    hourly: list[str] | None = None,
    daily: list[str] | None = None,
    current: bool = True,
    timezone: str = "auto",
    temperature_unit: str = "celsius",
    language: str = "de",
) -> dict:
    """
    Get weather from NOAA GFS model (global coverage).

    Args:
        location: City name or address (global coverage)
        days: Forecast days (1-16, default: 7)
        hourly: Hourly variables
        daily: Daily variables
        current: Include current weather
        timezone: Timezone for times
        temperature_unit: celsius or fahrenheit
        language: Language for descriptions (de or en, default: de)

    Returns:
        Weather forecast from NOAA GFS model
    """
    return await fetch_model_weather(
        location, API_URLS["gfs"], "NOAA GFS",
        days, hourly, daily, current, timezone, temperature_unit,
        language=language
    )


@mcp.tool()
async def get_meteofrance(
    location: str,
    days: int = 7,
    hourly: list[str] | None = None,
    daily: list[str] | None = None,
    current: bool = True,
    timezone: str = "auto",
    temperature_unit: str = "celsius",
    language: str = "de",
) -> dict:
    """
    Get weather from Météo-France AROME/ARPEGE model (France/Europe).

    Args:
        location: City name or address (best for France/Europe)
        days: Forecast days (1-16, default: 7)
        hourly: Hourly variables
        daily: Daily variables
        current: Include current weather
        timezone: Timezone for times
        temperature_unit: celsius or fahrenheit
        language: Language for descriptions (de or en, default: de)

    Returns:
        Weather forecast from Météo-France model
    """
    return await fetch_model_weather(
        location, API_URLS["meteofrance"], "Météo-France",
        days, hourly, daily, current, timezone, temperature_unit,
        language=language
    )


@mcp.tool()
async def get_ecmwf(
    location: str,
    days: int = 7,
    hourly: list[str] | None = None,
    daily: list[str] | None = None,
    current: bool = True,
    timezone: str = "auto",
    temperature_unit: str = "celsius",
    language: str = "de",
) -> dict:
    """
    Get weather from ECMWF model (European Centre, highly accurate).

    Args:
        location: City name or address (Europe-focused)
        days: Forecast days (1-16, default: 7)
        hourly: Hourly variables
        daily: Daily variables
        current: Include current weather
        timezone: Timezone for times
        temperature_unit: celsius or fahrenheit
        language: Language for descriptions (de or en, default: de)

    Returns:
        Weather forecast from ECMWF model
    """
    return await fetch_model_weather(
        location, API_URLS["ecmwf"], "ECMWF",
        days, hourly, daily, current, timezone, temperature_unit,
        language=language
    )


@mcp.tool()
async def get_jma(
    location: str,
    days: int = 7,
    hourly: list[str] | None = None,
    daily: list[str] | None = None,
    current: bool = True,
    timezone: str = "auto",
    temperature_unit: str = "celsius",
    language: str = "de",
) -> dict:
    """
    Get weather from JMA model (Japan Meteorological Agency, Asia-focused).

    Args:
        location: City name or address (best for Asia)
        days: Forecast days (1-16, default: 7)
        hourly: Hourly variables
        daily: Daily variables
        current: Include current weather
        timezone: Timezone for times
        temperature_unit: celsius or fahrenheit
        language: Language for descriptions (de or en, default: de)

    Returns:
        Weather forecast from JMA model
    """
    return await fetch_model_weather(
        location, API_URLS["jma"], "JMA",
        days, hourly, daily, current, timezone, temperature_unit,
        language=language
    )


@mcp.tool()
async def get_metno(
    location: str,
    days: int = 7,
    hourly: list[str] | None = None,
    daily: list[str] | None = None,
    current: bool = True,
    timezone: str = "auto",
    temperature_unit: str = "celsius",
    language: str = "de",
) -> dict:
    """
    Get weather from MET Norway model (Nordic countries).

    Args:
        location: City name or address (best for Nordic region)
        days: Forecast days (1-16, default: 7)
        hourly: Hourly variables
        daily: Daily variables
        current: Include current weather
        timezone: Timezone for times
        temperature_unit: celsius or fahrenheit
        language: Language for descriptions (de or en, default: de)

    Returns:
        Weather forecast from MET Norway model
    """
    return await fetch_model_weather(
        location, API_URLS["metno"], "MET Norway",
        days, hourly, daily, current, timezone, temperature_unit,
        language=language
    )


@mcp.tool()
async def get_gem(
    location: str,
    days: int = 7,
    hourly: list[str] | None = None,
    daily: list[str] | None = None,
    current: bool = True,
    timezone: str = "auto",
    temperature_unit: str = "celsius",
    language: str = "de",
) -> dict:
    """
    Get weather from Environment Canada GEM model (Canada-focused).

    Args:
        location: City name or address (best for Canada)
        days: Forecast days (1-16, default: 7)
        hourly: Hourly variables
        daily: Daily variables
        current: Include current weather
        timezone: Timezone for times
        temperature_unit: celsius or fahrenheit
        language: Language for descriptions (de or en, default: de)

    Returns:
        Weather forecast from Environment Canada GEM model
    """
    return await fetch_model_weather(
        location, API_URLS["gem"], "Environment Canada GEM",
        days, hourly, daily, current, timezone, temperature_unit,
        language=language
    )


# === Advanced Tools ===


@mcp.tool()
async def get_flood_forecast(
    location: str,
    daily: list[str] | None = None,
    forecast_days: int = 52,
    language: str = "de",
) -> dict:
    """
    Get river discharge/flood forecast for a location.

    Args:
        location: City name near a river
        daily: Daily variables (default: river_discharge)
        forecast_days: Forecast days (default: 52, max: 210)
        language: Language for location names (de or en, default: de)

    Returns:
        River discharge forecast data
    """
    try:
        geo = await geocode(location, language=language)
    except ValueError:
        return await handle_location_error(location, language)

    params = {
        "latitude": geo["latitude"],
        "longitude": geo["longitude"],
        "forecast_days": min(max(forecast_days, 1), 210),
    }

    if daily:
        params["daily"] = daily
    else:
        params["daily"] = ["river_discharge", "river_discharge_max", "river_discharge_min"]

    try:
        data = await fetch_api(API_URLS["flood"], params)
    except Exception as e:
        return await handle_api_error(e)

    result = {"location": format_location(geo)}

    daily_data = data.get("daily")
    if daily_data:
        time_list = daily_data.get("time", [])
        result["daily"] = [
            {
                "date": time_list[i],
                **{k: v[i] for k, v in daily_data.items() if k != "time" and i < len(v)},
            }
            for i in range(len(time_list))
        ]

    return result


@mcp.tool()
async def get_seasonal_forecast(
    location: str,
    monthly: list[str] | None = None,
    language: str = "de",
) -> dict:
    """
    Get seasonal forecast (6-9 months ahead).

    Args:
        location: City name or address
        monthly: Monthly variables (default: temperature, precipitation)
        language: Language for location names (de or en, default: de)

    Returns:
        Seasonal forecast with monthly aggregates
    """
    try:
        geo = await geocode(location, language=language)
    except ValueError:
        return await handle_location_error(location, language)

    params = {
        "latitude": geo["latitude"],
        "longitude": geo["longitude"],
    }

    # Note: Seasonal API uses 'sixhourly' not 'monthly' directly
    # We need to use appropriate parameters
    if monthly:
        params["sixhourly"] = monthly
    else:
        params["sixhourly"] = ["temperature_2m", "precipitation"]

    try:
        data = await fetch_api(API_URLS["seasonal"], params)
    except Exception as e:
        return await handle_api_error(e)

    result = {"location": format_location(geo)}

    # Format sixhourly data
    sixhourly = data.get("sixhourly")
    if sixhourly:
        time_list = sixhourly.get("time", [])
        result["forecast"] = [
            {
                "time": time_list[i],
                **{k: v[i] for k, v in sixhourly.items() if k != "time" and i < len(v)},
            }
            for i in range(len(time_list))
        ]

    return result


@mcp.tool()
async def get_climate_projection(
    location: str,
    start_date: str,
    end_date: str,
    models: list[str] | None = None,
    daily: list[str] | None = None,
    language: str = "de",
) -> dict:
    """
    Get CMIP6 climate projection data.

    Args:
        location: City name or address
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        models: Climate models (default: EC_Earth3P_HR)
        daily: Daily variables to retrieve
        language: Language for location names (de or en, default: de)

    Returns:
        Climate projection data for the specified period
    """
    try:
        geo = await geocode(location, language=language)
    except ValueError:
        return await handle_location_error(location, language)

    params = {
        "latitude": geo["latitude"],
        "longitude": geo["longitude"],
        "start_date": start_date,
        "end_date": end_date,
    }

    if models:
        params["models"] = models
    else:
        params["models"] = ["EC_Earth3P_HR"]

    if daily:
        params["daily"] = daily
    else:
        params["daily"] = [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
        ]

    try:
        data = await fetch_api(API_URLS["climate"], params)
    except Exception as e:
        return await handle_api_error(e)

    result = {"location": format_location(geo)}

    daily_data = data.get("daily")
    if daily_data:
        time_list = daily_data.get("time", [])
        result["daily"] = [
            {
                "date": time_list[i],
                **{k: v[i] for k, v in daily_data.items() if k != "time" and i < len(v)},
            }
            for i in range(len(time_list))
        ]

    return result


@mcp.tool()
async def get_ensemble_forecast(
    location: str,
    models: list[str] | None = None,
    hourly: list[str] | None = None,
    forecast_days: int = 7,
    timezone: str = "auto",
    language: str = "de",
) -> dict:
    """
    Get ensemble forecast from multiple models.

    Args:
        location: City name or address
        models: Ensemble models (default: icon_seamless)
        hourly: Hourly variables to retrieve
        forecast_days: Forecast days (default: 7)
        timezone: Timezone for times
        language: Language for location names (de or en, default: de)

    Returns:
        Ensemble forecast data from multiple model runs
    """
    try:
        geo = await geocode(location, language=language)
    except ValueError:
        return await handle_location_error(location, language)

    params = {
        "latitude": geo["latitude"],
        "longitude": geo["longitude"],
        "forecast_days": min(max(forecast_days, 1), 35),
        "timezone": timezone if timezone != "auto" else geo["timezone"],
    }

    if models:
        params["models"] = models
    else:
        params["models"] = ["icon_seamless"]

    if hourly:
        params["hourly"] = hourly
    else:
        params["hourly"] = ["temperature_2m", "precipitation"]

    try:
        data = await fetch_api(API_URLS["ensemble"], params)
    except Exception as e:
        return await handle_api_error(e)

    result = {"location": format_location(geo)}

    hourly_data = format_hourly_data(data)
    if hourly_data:
        result["hourly"] = hourly_data

    return result
