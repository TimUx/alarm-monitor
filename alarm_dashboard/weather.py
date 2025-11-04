"""Weather service integration using the open-meteo API."""

from __future__ import annotations

import logging
from typing import Dict, Optional

import requests

LOGGER = logging.getLogger(__name__)


class WeatherServiceError(RuntimeError):
    """Raised when weather retrieval fails."""


def fetch_weather(
    base_url: str,
    params_query: str,
    lat: float,
    lon: float,
) -> Optional[Dict[str, float]]:
    """Fetch current weather data for the provided coordinates."""

    params = {
        "latitude": lat,
        "longitude": lon,
    }
    for param in params_query.split("&"):
        if not param:
            continue
        if "=" in param:
            key, value = param.split("=", 1)
            params[key] = value
        else:
            params[param] = "true"

    LOGGER.debug(
        "Fetching weather for lat=%s lon=%s via %s", lat, lon, base_url
    )
    response = requests.get(base_url, params=params, timeout=10)
    if response.status_code != 200:
        raise WeatherServiceError(
            f"Weather API request failed with status {response.status_code}: {response.text}"
        )
    data = response.json()
    return data.get("current_weather")


__all__ = ["fetch_weather", "WeatherServiceError"]
