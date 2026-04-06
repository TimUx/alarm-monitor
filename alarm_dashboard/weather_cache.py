"""Weather data cache with background refresh and race-condition protection."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

LOGGER = logging.getLogger(__name__)


class WeatherCache:
    """Thread-safe weather data cache with background refresh."""

    def __init__(self, ttl_minutes: int = 5) -> None:
        self._lock = threading.Lock()
        self._cache: Dict[str, Any] = {}
        self._ttl = timedelta(minutes=ttl_minutes)

    def get_weather(
        self,
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

        with self._lock:
            cached_lat = self._cache.get("lat")
            cached_lon = self._cache.get("lon")
            fetched_at = self._cache.get("fetched_at")
            cached_data = self._cache.get("data")
            coords_match = cached_lat == lat and cached_lon == lon
            if coords_match and fetched_at and datetime.now(timezone.utc) - fetched_at < self._ttl:
                return cached_data
            stale = cached_data if coords_match else None
            already_fetching = self._cache.get("fetching", False)
            if already_fetching:
                return stale
            self._cache["fetching"] = True

        def _fetch() -> None:
            try:
                data = fetch_weather(weather_base_url, weather_params, lat, lon)
                with self._lock:
                    self._cache["lat"] = lat
                    self._cache["lon"] = lon
                    self._cache["data"] = data
                    self._cache["fetched_at"] = datetime.now(timezone.utc)
            except Exception as exc:  # pragma: no cover - best effort
                LOGGER.warning("Background weather fetch failed: %s", exc)
            finally:
                with self._lock:
                    self._cache["fetching"] = False

        if executor is not None:
            executor.submit(_fetch)
        else:
            threading.Thread(target=_fetch, daemon=True).start()

        return stale


# Module-level default instance for backwards compatibility
_default_cache = WeatherCache()


def get_cached_weather(
    weather_base_url: str,
    weather_params: str,
    lat: float,
    lon: float,
    executor: Any = None,
) -> Optional[Dict[str, Any]]:
    """Thin shim delegating to the module-level WeatherCache instance."""
    return _default_cache.get_weather(weather_base_url, weather_params, lat, lon, executor=executor)


__all__ = ["WeatherCache", "get_cached_weather"]
