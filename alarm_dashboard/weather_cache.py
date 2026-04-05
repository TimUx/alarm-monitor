"""Weather data cache with background refresh and race-condition protection."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

LOGGER = logging.getLogger(__name__)

_weather_cache_lock = threading.Lock()
_weather_cache: Dict[str, Any] = {}  # keys: lat, lon, data, fetched_at, fetching
_WEATHER_CACHE_TTL = timedelta(minutes=5)


def get_cached_weather(
    weather_base_url: str,
    weather_params: str,
    lat: float,
    lon: float,
    executor: Any = None,
) -> Optional[Dict[str, Any]]:
    """Return cached weather data if fresh, otherwise fetch in background and return stale/None.

    Args:
        weather_base_url: Base URL for the weather API.
        weather_params: Query string parameters for the weather API.
        lat: Latitude of the location.
        lon: Longitude of the location.
        executor: Optional ThreadPoolExecutor for background fetch. If None, a daemon thread is used.
    """
    from .weather import fetch_weather

    with _weather_cache_lock:
        cached_lat = _weather_cache.get("lat")
        cached_lon = _weather_cache.get("lon")
        fetched_at = _weather_cache.get("fetched_at")
        cached_data = _weather_cache.get("data")
        coords_match = cached_lat == lat and cached_lon == lon
        if coords_match and fetched_at and datetime.now(timezone.utc) - fetched_at < _WEATHER_CACHE_TTL:
            return cached_data
        stale = cached_data if coords_match else None
        already_fetching = _weather_cache.get("fetching", False)
        if already_fetching:
            return stale
        _weather_cache["fetching"] = True

    def _fetch() -> None:
        try:
            data = fetch_weather(weather_base_url, weather_params, lat, lon)
            with _weather_cache_lock:
                _weather_cache["lat"] = lat
                _weather_cache["lon"] = lon
                _weather_cache["data"] = data
                _weather_cache["fetched_at"] = datetime.now(timezone.utc)
        except Exception as exc:  # pragma: no cover - best effort
            LOGGER.warning("Background weather fetch failed: %s", exc)
        finally:
            with _weather_cache_lock:
                _weather_cache["fetching"] = False

    if executor is not None:
        executor.submit(_fetch)
    else:
        threading.Thread(target=_fetch, daemon=True).start()

    return stale


__all__ = ["get_cached_weather"]
