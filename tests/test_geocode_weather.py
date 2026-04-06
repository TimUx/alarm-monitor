"""Tests for geocode and weather modules."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from alarm_dashboard.geocode import geocode_location, GeocodingError
from alarm_dashboard.weather import fetch_weather, WeatherServiceError


class _MockResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code
        self.text = str(json_data)

    def json(self):
        return self._json


# ---------------------------------------------------------------------------
# Geocode tests
# ---------------------------------------------------------------------------


def test_geocode_location_returns_coordinates() -> None:
    """geocode_location should parse lat/lon from Nominatim response."""
    mock_session = MagicMock()
    mock_session.get.return_value = _MockResponse(
        [{"lat": "50.123", "lon": "9.456"}]
    )

    result = geocode_location("https://nominatim.test/search", "Test Street", session=mock_session)

    assert result is not None
    assert abs(result["lat"] - 50.123) < 0.001
    assert abs(result["lon"] - 9.456) < 0.001


def test_geocode_location_returns_none_when_no_results() -> None:
    """geocode_location should return None when Nominatim returns empty list."""
    mock_session = MagicMock()
    mock_session.get.return_value = _MockResponse([])

    result = geocode_location("https://nominatim.test/search", "Unknown Place", session=mock_session)

    assert result is None


def test_geocode_location_raises_on_error_status() -> None:
    """geocode_location should raise GeocodingError on non-200 response."""
    mock_session = MagicMock()
    mock_session.get.return_value = _MockResponse({}, status_code=500)

    with pytest.raises(GeocodingError):
        geocode_location("https://nominatim.test/search", "Test", session=mock_session)


def test_geocode_location_uses_thread_local_session_when_no_session_given() -> None:
    """geocode_location should create a thread-local session when none is provided."""
    from alarm_dashboard.geocode import _get_session
    session = _get_session()
    assert session is not None
    # Calling again should return the same session for this thread
    assert _get_session() is session


# ---------------------------------------------------------------------------
# Weather tests
# ---------------------------------------------------------------------------


def test_fetch_weather_returns_data() -> None:
    """fetch_weather should return parsed weather data from API."""
    mock_session = MagicMock()
    mock_session.get.return_value = _MockResponse({
        "current_weather": {
            "weathercode": 0,
            "temperature": 20.5,
            "windspeed": 5.0,
            "winddirection": 180.0,
        },
        "hourly": {
            "time": ["2024-01-01T00:00"],
            "precipitation": [0.0],
            "precipitation_probability": [10],
        }
    })

    result = fetch_weather(
        "https://api.open-meteo.com/v1/forecast",
        "current_weather=true",
        50.0,
        9.0,
        session=mock_session,
    )

    assert result is not None
    assert result["temperature"] == 20.5


def test_fetch_weather_raises_on_error_status() -> None:
    """fetch_weather should raise WeatherServiceError on non-200 response."""
    mock_session = MagicMock()
    mock_session.get.return_value = _MockResponse({}, status_code=500)

    with pytest.raises(WeatherServiceError):
        fetch_weather(
            "https://api.open-meteo.com/v1/forecast",
            "current_weather=true",
            50.0,
            9.0,
            session=mock_session,
        )


def test_fetch_weather_returns_none_when_no_current_weather() -> None:
    """fetch_weather should return None when current_weather is absent."""
    mock_session = MagicMock()
    mock_session.get.return_value = _MockResponse({"hourly": {}})

    result = fetch_weather(
        "https://api.open-meteo.com/v1/forecast",
        "current_weather=true",
        50.0,
        9.0,
        session=mock_session,
    )

    assert result is None


def test_fetch_weather_uses_thread_local_session_when_no_session_given() -> None:
    """fetch_weather should create a thread-local session when none is provided."""
    from alarm_dashboard.weather import _get_session
    session = _get_session()
    assert session is not None
    assert _get_session() is session
