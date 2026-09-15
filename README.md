# renfield-mcp-weather

A Python MCP (Model Context Protocol) server that provides weather data from the Open-Meteo API. It is based on the npm package `open-meteo-mcp-server` with an additional functionality for geocode lookups that makes it easier for small, local models to access data.

## Key Features

- All tools accept `location` (city name) instead of `latitude`/`longitude`
- Geocoding handled internally and transparently
- **Multilingual support** - weather descriptions in multiple languages
- Extensible language support without code changes

## Installation

```bash
pip install renfield-mcp-weather
```

## Usage

### As MCP Server (stdio transport)

```bash
python -m renfield_mcp_weather
```

### In MCP Configuration

```yaml
- name: weather
  transport: stdio
  command: python
  args: ["-m", "renfield_mcp_weather"]
```

## Multilingual Support

All tools support a `language` parameter (default: `"de"`).

Built-in languages: `de` (German), `en` (English), `fr` (French)

```python
# German (default)
result = await get_weather("Berlin")
# -> "weather_description": "Bedeckt"

# English
result = await get_weather("Berlin", language="en")
# -> "weather_description": "Overcast"

# French
result = await get_weather("Paris", language="fr")
# -> "weather_description": "Couvert"
```

### Adding New Languages

Add new languages by creating JSON files - no code changes required.

**Option 1: Add to package locales directory**
```
src/renfield_mcp_weather/locales/es.json
```

**Option 2: Use custom locales directory (for runtime additions)**
```bash
export OPEN_METEO_LOCALES_DIR=/path/to/custom/locales
```

**Locale file format (`es.json`):**
```json
{
  "language_name": "Español",
  "weather_codes": {
    "0": "Cielo despejado",
    "1": "Mayormente despejado",
    "2": "Parcialmente nublado",
    "3": "Nublado",
    "45": "Niebla",
    "61": "Lluvia ligera",
    "95": "Tormenta"
  },
  "errors": {
    "location_not_found": "Ubicación no encontrada: {location}",
    "location_suggestion": "Pruebe con una ciudad más grande cercana",
    "unknown_weather": "Desconocido ({code})"
  }
}
```

## Available Tools

### Core Tools

| Tool | Description |
|------|-------------|
| `get_weather` | Current weather + forecast (1-16 days) |
| `get_weather_archive` | Historical weather data (1940-present) |
| `get_air_quality` | Air quality index, PM2.5, PM10, ozone |
| `get_marine_weather` | Wave height, sea conditions |
| `get_elevation` | Elevation at location |
| `geocode_location` | Resolve location name to coordinates |

### Weather Models

| Tool | Model | Best Coverage |
|------|-------|---------------|
| `get_dwd_icon` | DWD ICON | Germany/Europe |
| `get_gfs` | NOAA GFS | Global |
| `get_meteofrance` | Météo-France | France/Europe |
| `get_ecmwf` | ECMWF | Europe |
| `get_jma` | JMA | Asia |
| `get_metno` | MET Norway | Nordic |
| `get_gem` | Environment Canada | Canada |

### Advanced Tools

| Tool | Description |
|------|-------------|
| `get_flood_forecast` | River discharge forecasts |
| `get_seasonal_forecast` | 6-9 month forecasts |
| `get_climate_projection` | CMIP6 climate scenarios |
| `get_ensemble_forecast` | Multi-model ensemble |

## Example

```python
# Weather for Berlin with 7-day forecast (German)
result = await get_weather("Berlin")

# Weather in English
result = await get_weather("London", language="en")

# Historical data
result = await get_weather_archive("Munich", "2024-01-01", "2024-01-31")

# Air quality
result = await get_air_quality("Stuttgart")
```

## Response Format

Responses are compact and LLM-friendly:

```json
{
  "location": {"name": "Berlin", "country": "Germany"},
  "current": {
    "temperature": 8.2,
    "weather_code": 3,
    "weather_description": "Overcast",
    "wind_speed": 12.5
  },
  "daily": [
    {"date": "2024-02-06", "temp_max": 10, "temp_min": 4, "precipitation": 0.2}
  ]
}
```

### Errors

Errors are returned as a result with an `error` key (not as a raised tool error):

```json
{"error": "Weather API error: 500"}
{"error": "Weather API timeout - please try again"}
```

An upstream **throttle (HTTP 429)** is structured so a client can recognise it
without reading prose, and back off for as long as the upstream asked:

```json
{"error": "Weather API rate limit (HTTP 429)", "status": 429, "retry_after": 30}
```

`retry_after` (seconds) is present only when Open-Meteo sent a numeric
`Retry-After` header; the HTTP-date form is omitted rather than guessed. A bare
"429" in a message is deliberately not the signal — it could be a postcode.

## Configuration

All configuration is externalized in JSON files - no code changes required.

### API URLs

API endpoints are configured in `config/api_urls.json`. Override without rebuilding:

**Option 1: Custom config file**
```bash
export OPEN_METEO_CONFIG_FILE=/path/to/custom/api_urls.json
```

**Option 2: Individual URL overrides**
```bash
export OPEN_METEO_API_URL_FORECAST=https://my-instance.com/v1/forecast
export OPEN_METEO_API_URL_GEOCODING=https://my-instance.com/v1/search
```

**Config file format (`api_urls.json`):**
```json
{
  "forecast": "https://api.open-meteo.com/v1/forecast",
  "archive": "https://archive-api.open-meteo.com/v1/archive",
  "air_quality": "https://air-quality-api.open-meteo.com/v1/air-quality",
  "geocoding": "https://geocoding-api.open-meteo.com/v1/search",
  "dwd_icon": "https://api.open-meteo.com/v1/dwd-icon"
}
```

## Environment Variables

```bash
# Custom API config file
OPEN_METEO_CONFIG_FILE=/path/to/api_urls.json

# Individual API URL overrides
OPEN_METEO_API_URL_FORECAST=https://custom.api/v1/forecast
OPEN_METEO_API_URL_GEOCODING=https://custom.api/v1/search

# Legacy: Override base URL for main APIs
OPEN_METEO_API_URL=https://api.open-meteo.com

# Default language for all tools
OPEN_METEO_LANGUAGE=de

# Custom locales directory (for adding languages at runtime)
OPEN_METEO_LOCALES_DIR=/path/to/locales
```

## Development

```bash
# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check src/
ruff format src/
```
## Reference

- Open-Meteo API Docs: https://open-meteo.com/en/docs
- MCP SDK: https://github.com/modelcontextprotocol/python-sdk
- FastMCP: https://github.com/jlowin/fastmcp
- npm package `open-meteo-mcp-server`  https://github.com/cmer81/open-meteo-mcp
## License

MIT
