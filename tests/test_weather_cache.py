"""Tests for WeatherCache class."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from alarm_dashboard.weather_cache import WeatherCache


_SAMPLE_WEATHER = {"weathercode": 0, "temperature": 20.0, "windspeed": 5.0, "winddirection": 180.0}


def test_cache_hit_returns_cached_data() -> None:
    """Pre-populated cache should return data without calling fetch_weather."""
    cache = WeatherCache(ttl_minutes=5)
    # Pre-populate the cache
    cache._cache = {
        "lat": 50.0,
        "lon": 9.0,
        "data": _SAMPLE_WEATHER,
        "fetched_at": datetime.now(timezone.utc),
        "fetching": False,
    }

    with patch("alarm_dashboard.weather.fetch_weather") as mock_fetch:
        result = cache.get_weather("http://weather", "params", 50.0, 9.0)

    assert result == _SAMPLE_WEATHER
    mock_fetch.assert_not_called()


def test_cache_miss_returns_none_and_triggers_background_fetch() -> None:
    """Empty cache should return None and submit a background fetch."""
    cache = WeatherCache(ttl_minutes=5)
    mock_executor = MagicMock()

    result = cache.get_weather("http://weather", "params", 50.0, 9.0, executor=mock_executor)

    assert result is None
    mock_executor.submit.assert_called_once()


def test_cache_returns_stale_while_revalidating() -> None:
    """Expired cache should return stale data while triggering a background refresh."""
    cache = WeatherCache(ttl_minutes=5)
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    cache._cache = {
        "lat": 50.0,
        "lon": 9.0,
        "data": _SAMPLE_WEATHER,
        "fetched_at": stale_time,
        "fetching": False,
    }
    mock_executor = MagicMock()

    result = cache.get_weather("http://weather", "params", 50.0, 9.0, executor=mock_executor)

    assert result == _SAMPLE_WEATHER  # Returns stale data
    mock_executor.submit.assert_called_once()  # Triggers background fetch


def test_cache_already_fetching_guard_prevents_duplicate_fetch() -> None:
    """If a fetch is already in progress, no additional fetch should be started."""
    cache = WeatherCache(ttl_minutes=5)
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    cache._cache = {
        "lat": 50.0,
        "lon": 9.0,
        "data": _SAMPLE_WEATHER,
        "fetched_at": stale_time,
        "fetching": True,  # Already fetching
    }
    mock_executor = MagicMock()

    result = cache.get_weather("http://weather", "params", 50.0, 9.0, executor=mock_executor)

    assert result == _SAMPLE_WEATHER  # Returns stale
    mock_executor.submit.assert_not_called()  # No duplicate fetch


def test_cache_ttl_expiry_triggers_new_fetch() -> None:
    """Data older than TTL should trigger a new background fetch."""
    cache = WeatherCache(ttl_minutes=1)
    expired_time = datetime.now(timezone.utc) - timedelta(minutes=2)
    cache._cache = {
        "lat": 51.0,
        "lon": 10.0,
        "data": _SAMPLE_WEATHER,
        "fetched_at": expired_time,
        "fetching": False,
    }
    mock_executor = MagicMock()

    result = cache.get_weather("http://weather", "params", 51.0, 10.0, executor=mock_executor)

    assert result == _SAMPLE_WEATHER  # Returns stale
    mock_executor.submit.assert_called_once()  # Triggers new fetch
