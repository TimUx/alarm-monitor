"""Tests for DWD warnings integration."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alarm_dashboard.bundesland import resolve_dwd_region
from alarm_dashboard.dwd_warnings import (
    SEVERE_WARNING_MIN_LEVEL,
    build_mock_severe_warnings,
    warnings_for_location,
)
from alarm_dashboard.warnings_cache import WarningsCache


def _sample_polygon(lon: float, lat: float) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[
            [lon - 0.1, lat - 0.1],
            [lon + 0.1, lat - 0.1],
            [lon + 0.1, lat + 0.1],
            [lon - 0.1, lat + 0.1],
            [lon - 0.1, lat - 0.1],
        ]],
    }


def _sample_payload(lat: float, lon: float, *, level: int = 3) -> dict:
    now_ms = 1_700_000_000_000
    return {
        "time": now_ms,
        "warnings": [
            {
                "warnId": "test-warning",
                "type": 0,
                "level": level,
                "start": now_ms - 60_000,
                "end": now_ms + 3_600_000,
                "event": "STURMBÖEN",
                "headLine": "Amtliche UNWETTERWARNUNG vor STURMBÖEN",
                "description": "Es treten Sturmböen auf.",
                "regions": [
                    {"polygonGeometry": _sample_polygon(lon, lat)},
                ],
            },
        ],
    }


def test_resolve_dwd_region_for_hessen() -> None:
    region = resolve_dwd_region(50.55, 9.0)
    assert region is not None
    assert region.code == "hes"
    assert region.name == "Hessen"


def test_warnings_for_location_returns_active_severe_warning() -> None:
    lat, lon = 50.55, 9.0
    payload = _sample_payload(lat, lon, level=3)
    now_ms = payload["time"]

    result = warnings_for_location(payload, lat, lon, now_ms=now_ms)

    assert result["active"] is True
    assert result["bundesland"]["code"] == "hes"
    assert result["map_url"].endswith("warnungen_gemeinde_map_hes.png")
    assert len(result["items"]) == 1
    assert result["items"][0]["headline"].startswith("Amtliche UNWETTERWARNUNG")
    assert result["items"][0]["level"] == 3


def test_warnings_for_location_ignores_lower_levels() -> None:
    lat, lon = 50.55, 9.0
    payload = _sample_payload(lat, lon, level=2)
    now_ms = payload["time"]

    result = warnings_for_location(payload, lat, lon, now_ms=now_ms)

    assert result["active"] is False
    assert result["items"] == []


def test_warnings_for_location_ignores_outside_polygon() -> None:
    payload = _sample_payload(50.55, 9.0, level=4)
    now_ms = payload["time"]

    result = warnings_for_location(payload, 48.0, 11.0, now_ms=now_ms)

    assert result["active"] is False
    assert result["items"] == []


def test_warnings_cache_returns_filtered_warnings() -> None:
    from datetime import datetime, timezone

    lat, lon = 50.55, 9.0
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    payload = _sample_payload(lat, lon, level=SEVERE_WARNING_MIN_LEVEL)
    payload["time"] = now_ms
    payload["warnings"][0]["start"] = now_ms - 60_000
    payload["warnings"][0]["end"] = now_ms + 3_600_000
    cache = WarningsCache(ttl_minutes=10)
    cache._cache = {
        "url": "http://dwd.test/warnings.json",
        "data": payload,
        "fetched_at": datetime.now(timezone.utc),
        "fetching": False,
    }

    result = cache.get_warnings_for_coordinates("http://dwd.test/warnings.json", lat, lon)

    assert result is not None
    assert result["active"] is True
    assert len(result["items"]) == 1


def test_warnings_cache_miss_triggers_background_fetch() -> None:
    cache = WarningsCache(ttl_minutes=10)
    mock_executor = MagicMock()

    result = cache.get_warnings_for_coordinates(
        "http://dwd.test/warnings.json",
        50.55,
        9.0,
        executor=mock_executor,
    )

    assert result is None
    mock_executor.submit.assert_called_once()


def test_build_mock_severe_warnings_returns_active_warning() -> None:
    result = build_mock_severe_warnings(50.55, 9.0)

    assert result["active"] is True
    assert result["mock"] is True
    assert result["bundesland"]["code"] == "hes"
    assert len(result["items"]) == 1
    assert result["items"][0]["level"] == 3
    assert "Simulierte Testwarnung" in result["items"][0]["description"]


def test_fetch_warnings_payload_decompresses_gzip() -> None:
    import gzip
    import json

    from alarm_dashboard.dwd_warnings import fetch_warnings_payload

    payload = {"warnings": []}
    body = gzip.compress(json.dumps(payload).encode("utf-8"))
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = body

    mock_session = MagicMock()
    mock_session.get.return_value = mock_response

    result = fetch_warnings_payload("http://dwd.test/warnings.json", session=mock_session)

    assert result == payload
