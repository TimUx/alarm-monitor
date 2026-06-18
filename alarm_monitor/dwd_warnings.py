"""DWD severe weather warnings integration (WarnWetter API)."""

from __future__ import annotations

import gzip
import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

import requests

from .bundesland import (
    WARNING_LEVEL_LABELS,
    dwd_map_url,
    resolve_dwd_region,
    warning_map_legend,
)

LOGGER = logging.getLogger(__name__)

_local = threading.local()

# Unwetterwarnungen (Stufe 3) and extrem (Stufe 4)
SEVERE_WARNING_MIN_LEVEL = 3

DEFAULT_DWD_WARNINGS_URL = (
    "https://s3.eu-central-1.amazonaws.com/app-prod-static.warnwetter.de/v16/"
    "gemeinde_warnings_v2.json"
)


class DwdWarningsError(RuntimeError):
    """Raised when DWD warning retrieval fails."""


def _get_session() -> requests.Session:
    if not hasattr(_local, "session"):
        _local.session = requests.Session()
    return _local.session


def _point_in_ring(lon: float, lat: float, ring: Sequence[Sequence[float]]) -> bool:
    """Ray-casting point-in-polygon test for a single GeoJSON ring."""
    inside = False
    count = len(ring)
    if count < 3:
        return False

    j = count - 1
    for i in range(count):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        intersects = ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-15) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _point_in_polygon_geometry(lon: float, lat: float, geometry: Dict[str, Any]) -> bool:
    if not geometry or geometry.get("type") != "Polygon":
        return False
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or not coordinates:
        return False
    outer_ring = coordinates[0]
    if not isinstance(outer_ring, list):
        return False
    return _point_in_ring(lon, lat, outer_ring)


def _warning_affects_point(
    warning: Dict[str, Any],
    lat: float,
    lon: float,
    now_ms: int,
) -> bool:
    start = warning.get("start")
    end = warning.get("end")
    if not isinstance(start, int) or not isinstance(end, int):
        return False
    if now_ms < start or now_ms > end:
        return False

    regions = warning.get("regions")
    if not isinstance(regions, list):
        return False

    for region in regions:
        if not isinstance(region, dict):
            continue
        geometry = region.get("polygonGeometry")
        if isinstance(geometry, dict) and _point_in_polygon_geometry(lon, lat, geometry):
            return True
    return False


def _format_timestamp(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def _serialize_warning(warning: Dict[str, Any]) -> Dict[str, Any]:
    level = warning.get("level")
    level_int = int(level) if isinstance(level, int) else 0
    start = warning.get("start")
    end = warning.get("end")

    return {
        "headline": warning.get("headLine") or warning.get("headline"),
        "event": warning.get("event"),
        "level": level_int,
        "level_label": WARNING_LEVEL_LABELS.get(level_int, "Warnung"),
        "description": warning.get("description") or warning.get("descriptionText"),
        "instruction": warning.get("instruction"),
        "start": _format_timestamp(start) if isinstance(start, int) else None,
        "end": _format_timestamp(end) if isinstance(end, int) else None,
    }


def fetch_warnings_payload(
    base_url: str = DEFAULT_DWD_WARNINGS_URL,
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    """Fetch the national DWD Gemeinde warnings JSON payload."""
    _session = session if session is not None else _get_session()
    response = _session.get(
        base_url,
        timeout=15,
        headers={"Accept-Encoding": "gzip"},
    )
    if response.status_code != 200:
        raise DwdWarningsError(
            f"DWD warnings request failed with status {response.status_code}"
        )

    content = response.content
    if content[:2] == b"\x1f\x8b":
        content = gzip.decompress(content)

    payload = json.loads(content.decode("utf-8"))

    if not isinstance(payload, dict):
        raise DwdWarningsError("Unexpected DWD warnings payload format")
    return payload


def warnings_for_location(
    payload: Dict[str, Any],
    lat: float,
    lon: float,
    *,
    min_level: int = SEVERE_WARNING_MIN_LEVEL,
    now_ms: Optional[int] = None,
) -> Dict[str, Any]:
    """Filter active severe warnings for a coordinate from a DWD payload."""
    region = resolve_dwd_region(lat, lon)
    region_code = region.code if region else None
    region_name = region.name if region else None

    result: Dict[str, Any] = {
        "active": False,
        "bundesland": {
            "code": region_code,
            "name": region_name,
        }
        if region
        else None,
        "map_url": dwd_map_url(region_code) if region_code else None,
        "map_legend": warning_map_legend(),
        "items": [],
    }

    warnings = payload.get("warnings")
    if not isinstance(warnings, list):
        return result

    current_ms = now_ms if now_ms is not None else int(datetime.now(timezone.utc).timestamp() * 1000)
    matched: List[Dict[str, Any]] = []

    for warning in warnings:
        if not isinstance(warning, dict):
            continue
        level = warning.get("level")
        if not isinstance(level, int) or level < min_level:
            continue
        if not _warning_affects_point(warning, lat, lon, current_ms):
            continue
        matched.append(_serialize_warning(warning))

    matched.sort(key=lambda item: item.get("level", 0), reverse=True)
    result["items"] = matched
    result["active"] = len(matched) > 0
    return result


def get_warnings_for_coordinates(
    lat: float,
    lon: float,
    base_url: str = DEFAULT_DWD_WARNINGS_URL,
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    """Fetch DWD warnings and return active severe warnings for coordinates."""
    payload = fetch_warnings_payload(base_url, session=session)
    return warnings_for_location(payload, lat, lon)


def build_mock_severe_warnings(lat: float, lon: float) -> Dict[str, Any]:
    """Return a simulated level-3 severe weather warning for UI testing."""
    region = resolve_dwd_region(lat, lon)
    region_code = region.code if region else "hes"
    region_name = region.name if region else "Hessen"
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=1)
    end = now + timedelta(hours=6)

    return {
        "active": True,
        "mock": True,
        "bundesland": {
            "code": region_code,
            "name": region_name,
        },
        "map_url": dwd_map_url(region_code),
        "map_legend": warning_map_legend(),
        "items": [
            {
                "headline": "Amtliche UNWETTERWARNUNG vor STURMBÖEN",
                "event": "STURMBÖEN",
                "level": 3,
                "level_label": WARNING_LEVEL_LABELS[3],
                "description": (
                    "Simulierte Testwarnung: Es treten Sturmböen mit Geschwindigkeiten "
                    "bis 90 km/h (25 m/s, 48 kn, Bft 10) auf."
                ),
                "instruction": (
                    "Dies ist nur ein Test. Aufenthalt im Freien vermeiden; "
                    "lose Gegenstände sichern."
                ),
                "start": start.isoformat(),
                "end": end.isoformat(),
            }
        ],
    }


__all__ = [
    "DEFAULT_DWD_WARNINGS_URL",
    "DwdWarningsError",
    "SEVERE_WARNING_MIN_LEVEL",
    "build_mock_severe_warnings",
    "fetch_warnings_payload",
    "get_warnings_for_coordinates",
    "warnings_for_location",
]
