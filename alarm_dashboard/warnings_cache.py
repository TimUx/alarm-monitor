"""DWD warnings cache with background refresh."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

LOGGER = logging.getLogger(__name__)


class WarningsCache:
    """Thread-safe cache for the national DWD warnings payload."""

    def __init__(self, ttl_minutes: int = 10) -> None:
        self._lock = threading.Lock()
        self._cache: Dict[str, Any] = {}
        self._ttl = timedelta(minutes=ttl_minutes)

    def get_payload(
        self,
        warnings_base_url: str,
        executor: Any = None,
    ) -> Optional[Dict[str, Any]]:
        """Return cached DWD payload if fresh, otherwise refresh in background."""
        from .dwd_warnings import fetch_warnings_payload

        with self._lock:
            fetched_at = self._cache.get("fetched_at")
            cached_url = self._cache.get("url")
            cached_data = self._cache.get("data")
            url_match = cached_url == warnings_base_url
            if (
                url_match
                and fetched_at
                and datetime.now(timezone.utc) - fetched_at < self._ttl
            ):
                return cached_data
            stale = cached_data if url_match else None
            already_fetching = self._cache.get("fetching", False)
            if already_fetching:
                return stale
            self._cache["fetching"] = True

        def _fetch() -> None:
            try:
                data = fetch_warnings_payload(warnings_base_url)
                with self._lock:
                    self._cache["url"] = warnings_base_url
                    self._cache["data"] = data
                    self._cache["fetched_at"] = datetime.now(timezone.utc)
            except Exception as exc:  # pragma: no cover - best effort
                LOGGER.warning("Background DWD warnings fetch failed: %s", exc)
            finally:
                with self._lock:
                    self._cache["fetching"] = False

        if executor is not None:
            executor.submit(_fetch)
        else:
            threading.Thread(target=_fetch, daemon=True).start()

        return stale

    def get_warnings_for_coordinates(
        self,
        warnings_base_url: str,
        lat: float,
        lon: float,
        executor: Any = None,
    ) -> Optional[Dict[str, Any]]:
        """Return active severe warnings for coordinates using cached payload."""
        from .dwd_warnings import warnings_for_location

        payload = self.get_payload(warnings_base_url, executor=executor)
        if payload is None:
            return None
        return warnings_for_location(payload, lat, lon)


_default_cache = WarningsCache()


def get_cached_warnings(
    warnings_base_url: str,
    lat: float,
    lon: float,
    executor: Any = None,
) -> Optional[Dict[str, Any]]:
    """Thin shim delegating to the module-level WarningsCache instance."""
    return _default_cache.get_warnings_for_coordinates(
        warnings_base_url,
        lat,
        lon,
        executor=executor,
    )


__all__ = ["WarningsCache", "get_cached_warnings"]
