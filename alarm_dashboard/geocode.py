"""Geocoding helper for translating addresses into coordinates."""

from __future__ import annotations

import logging
from typing import Dict, Optional

import requests

LOGGER = logging.getLogger(__name__)

# User-Agent header required by Nominatim usage policy
# https://operations.osmfoundation.org/policies/nominatim/
DEFAULT_USER_AGENT = "AlarmDashboard/1.0"

_session: requests.Session = requests.Session()


class GeocodingError(RuntimeError):
    """Raised when the geocoding service returns an error."""


def geocode_location(
    base_url: str,
    location: str,
    session: Optional[requests.Session] = None,
) -> Optional[Dict[str, float]]:
    """Resolve a human readable location into latitude and longitude."""

    _s = session if session is not None else _session
    params = {
        "q": location,
        "format": "json",
        "limit": 1,
    }
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
    }
    LOGGER.debug("Geocoding location '%s' via %s", location, base_url)
    response = _s.get(base_url, params=params, headers=headers, timeout=10)
    if response.status_code != 200:
        raise GeocodingError(
            f"Geocoding request failed with status {response.status_code}: {response.text}"
        )
    results = response.json()
    if not results:
        LOGGER.warning("No geocoding results for location '%s'", location)
        return None
    result = results[0]
    return {"lat": float(result["lat"]), "lon": float(result["lon"])}


__all__ = ["geocode_location", "GeocodingError"]
