"""Weather service integration using the open-meteo API."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

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

    current_raw = data.get("current_weather")
    if isinstance(current_raw, dict):
        current: Optional[Dict[str, float]] = dict(current_raw)
    else:
        current_data = data.get("current")
        current = dict(current_data) if isinstance(current_data, dict) else None

    if not current:
        return None

    time_value = current.get("time")
    hourly: Optional[Dict[str, List[Any]]] = (
        data.get("hourly") if isinstance(data.get("hourly"), dict) else None
    )
    hourly_units: Optional[Dict[str, str]] = (
        data.get("hourly_units") if isinstance(data.get("hourly_units"), dict) else None
    )

    if (
        hourly
        and isinstance(time_value, str)
        and isinstance(hourly.get("time"), list)
    ):
        try:
            index = hourly["time"].index(time_value)
        except ValueError:
            index = None

        if index is None and hourly.get("time"):
            index = len(hourly["time"]) - 1

        if index is not None:
            enrichment_fields = [
                "precipitation",
                "rain",
                "showers",
                "snowfall",
                "precipitation_probability",
            ]
            for field in enrichment_fields:
                values = hourly.get(field)
                if not isinstance(values, list) or index >= len(values):
                    continue
                value = values[index]
                if value is None:
                    continue
                current[field] = value
                if hourly_units and field in hourly_units:
                    current[f"{field}_unit"] = hourly_units[field]

    return current


__all__ = ["fetch_weather", "WeatherServiceError"]
