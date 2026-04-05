"""Tests for the Flask application factory (API endpoint architecture)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from alarm_dashboard.config import AppConfig
from alarm_dashboard import app as app_module


API_KEY = "test-secret-key"
SETTINGS_PASSWORD = "test-settings-password"


@pytest.fixture(autouse=True)
def mock_network_calls():
    """Prevent real network calls by patching geocode and weather helpers."""
    with (
        patch("alarm_dashboard.geocode.geocode_location", return_value=None),
        patch("alarm_dashboard.weather.fetch_weather", return_value=None),
    ):
        yield


@pytest.fixture
def config(tmp_path: Path) -> AppConfig:
    """Return an AppConfig with a known API key and temp history file."""
    return AppConfig(
        api_key=API_KEY,
        settings_password=SETTINGS_PASSWORD,
        history_file=str(tmp_path / "history.json"),
        settings_file=str(tmp_path / "settings.json"),
        display_duration_minutes=30,
    )


@pytest.fixture
def flask_app(config: AppConfig):
    """Create a Flask test application."""
    application = app_module.create_app(config)
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(flask_app):
    """Return a Flask test client."""
    return flask_app.test_client()


# ---------------------------------------------------------------------------
# POST /api/alarm – authentication
# ---------------------------------------------------------------------------


def test_post_alarm_with_correct_api_key_stores_alarm(client, flask_app) -> None:
    """POST /api/alarm with correct API key should accept and store the alarm."""
    alarm_data = {
        "incident_number": "12345",
        "keyword": "F3Y",
        "location": "Musterstraße 1, Musterstadt",
    }

    response = client.post(
        "/api/alarm",
        json=alarm_data,
        headers={"X-API-Key": API_KEY},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"

    store = flask_app.config["ALARM_STORE"]
    history = store.history()
    assert len(history) == 1
    assert history[0]["alarm"]["incident_number"] == "12345"


def test_post_alarm_with_wrong_api_key_returns_401(client) -> None:
    """POST /api/alarm with an incorrect API key should return 401."""
    alarm_data = {"incident_number": "99999", "keyword": "F1"}

    response = client.post(
        "/api/alarm",
        json=alarm_data,
        headers={"X-API-Key": "wrong-key"},
    )

    assert response.status_code == 401
    data = response.get_json()
    assert "error" in data


def test_post_alarm_with_missing_api_key_returns_401(client) -> None:
    """POST /api/alarm without X-API-Key header should return 401."""
    alarm_data = {"incident_number": "99999", "keyword": "F1"}

    response = client.post("/api/alarm", json=alarm_data)

    assert response.status_code == 401
    data = response.get_json()
    assert "error" in data


def test_post_alarm_with_no_json_body_returns_400(client) -> None:
    """POST /api/alarm with correct API key but empty JSON body should return 400."""
    response = client.post(
        "/api/alarm",
        json={},
        headers={"X-API-Key": API_KEY},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data


# ---------------------------------------------------------------------------
# POST /api/alarm – business logic
# ---------------------------------------------------------------------------


def test_post_alarm_duplicate_incident_number_rejected(client, flask_app) -> None:
    """A second alarm with the same incident_number should be silently dropped."""
    alarm_data = {"incident_number": "12345", "keyword": "F3Y"}

    client.post("/api/alarm", json=alarm_data, headers={"X-API-Key": API_KEY})
    response = client.post(
        "/api/alarm",
        json={"incident_number": "12345", "keyword": "F4Y"},
        headers={"X-API-Key": API_KEY},
    )

    assert response.status_code == 200
    store = flask_app.config["ALARM_STORE"]
    history = store.history()
    assert len(history) == 1
    assert history[0]["alarm"]["keyword"] == "F3Y"


def test_post_alarm_without_incident_number_rejected(client, flask_app) -> None:
    """An alarm payload missing incident_number should be accepted at the HTTP level
    but not stored (process_alarm silently drops it)."""
    alarm_data = {"keyword": "F3Y", "location": "Somewhere"}

    response = client.post(
        "/api/alarm",
        json=alarm_data,
        headers={"X-API-Key": API_KEY},
    )

    assert response.status_code == 200
    store = flask_app.config["ALARM_STORE"]
    assert store.history() == []


# ---------------------------------------------------------------------------
# GET /api/alarm – idle / alarm modes
# ---------------------------------------------------------------------------


def test_get_alarm_returns_idle_when_no_alarm(client) -> None:
    """GET /api/alarm should return mode=idle when no alarm has been stored."""
    response = client.get("/api/alarm")

    assert response.status_code == 200
    data = response.get_json()
    assert data["mode"] == "idle"
    assert data["alarm"] is None


def test_get_alarm_returns_alarm_data_when_active(client, flask_app) -> None:
    """GET /api/alarm should return mode=alarm while the alarm is within the display window."""
    alarm_data = {"incident_number": "77777", "keyword": "F3Y"}

    client.post("/api/alarm", json=alarm_data, headers={"X-API-Key": API_KEY})

    response = client.get("/api/alarm")

    assert response.status_code == 200
    data = response.get_json()
    assert data["mode"] == "alarm"
    assert data["alarm"]["incident_number"] == "77777"


def test_get_alarm_returns_idle_after_display_duration_expires(
    client, flask_app, config: AppConfig
) -> None:
    """GET /api/alarm should return mode=idle once the display_duration has passed."""
    alarm_data = {"incident_number": "55555", "keyword": "B2"}

    client.post("/api/alarm", json=alarm_data, headers={"X-API-Key": API_KEY})

    store = flask_app.config["ALARM_STORE"]
    past_time = datetime.now(timezone.utc) - timedelta(minutes=config.display_duration_minutes + 1)
    with store._lock:
        store._alarm["received_at"] = past_time
        store._history[0]["received_at"] = past_time

    response = client.get("/api/alarm")

    assert response.status_code == 200
    data = response.get_json()
    assert data["mode"] == "idle"


# ---------------------------------------------------------------------------
# Misc / integration
# ---------------------------------------------------------------------------


def test_create_app_uses_instance_history_path() -> None:
    """A default history file should be created inside the instance folder."""
    cfg = AppConfig(api_key=None, history_file=None)
    flask_app = app_module.create_app(cfg)

    store = flask_app.config["ALARM_STORE"]
    expected_path = Path(flask_app.instance_path) / "alarm_history.json"

    assert store._persistence_path == expected_path  # type: ignore[attr-defined]
    assert cfg.history_file == str(expected_path)


def test_history_persists_between_app_instances(tmp_path: Path) -> None:
    """Entries written by one app instance should be visible in a new instance."""
    history_file = tmp_path / "history.json"
    cfg = AppConfig(api_key=API_KEY, history_file=str(history_file))

    first_app = app_module.create_app(cfg)
    first_store = first_app.config["ALARM_STORE"]
    first_store.update({"alarm": {"keyword": "Persist", "incident_number": "1"}})

    second_app = app_module.create_app(cfg)
    second_store = second_app.config["ALARM_STORE"]

    history = second_store.history()
    assert history
    assert history[0]["alarm"]["keyword"] == "Persist"


def test_create_app_initializes_messenger_when_configured(tmp_path: Path) -> None:
    """The app should initialize messenger when both URL and API key are provided."""
    cfg = AppConfig(
        api_key=API_KEY,
        messenger_server_url="https://messenger.example.com",
        messenger_api_key="test-key-123",
        history_file=str(tmp_path / "history.json"),
    )

    application = app_module.create_app(cfg)
    messenger = application.config.get("ALARM_MESSENGER")

    assert messenger is not None
    assert messenger.config.server_url == "https://messenger.example.com"
    assert messenger.config.api_key == "test-key-123"


def test_create_app_does_not_initialize_messenger_without_url(tmp_path: Path) -> None:
    """The app should not initialize messenger when URL is not provided."""
    cfg = AppConfig(
        api_key=API_KEY,
        messenger_server_url=None,
        messenger_api_key="test-key-123",
        history_file=str(tmp_path / "history.json"),
    )

    application = app_module.create_app(cfg)
    messenger = application.config.get("ALARM_MESSENGER")

    assert messenger is None


def test_create_app_does_not_initialize_messenger_without_api_key(tmp_path: Path) -> None:
    """The app should not initialize messenger when API key is not provided."""
    cfg = AppConfig(
        api_key=API_KEY,
        messenger_server_url="https://messenger.example.com",
        messenger_api_key=None,
        history_file=str(tmp_path / "history.json"),
    )

    application = app_module.create_app(cfg)
    messenger = application.config.get("ALARM_MESSENGER")

    assert messenger is None




# ---------------------------------------------------------------------------
# GET /api/settings – returns defaults
# ---------------------------------------------------------------------------


def test_get_settings_returns_defaults(client) -> None:
    """GET /api/settings should return the default setting values."""
    response = client.get("/api/settings")

    assert response.status_code == 200
    data = response.get_json()
    assert "fire_department_name" in data
    assert "default_latitude" in data
    assert "default_longitude" in data
    assert "default_location_name" in data
    assert "activation_groups" in data


# ---------------------------------------------------------------------------
# POST /api/settings – authentication and update
# ---------------------------------------------------------------------------


def test_post_settings_updates_values(client, flask_app) -> None:
    """POST /api/settings with correct settings password should update the settings."""
    payload = {
        "fire_department_name": "Test Feuerwehr",
        "activation_groups": "WIL26,WIL41",
    }

    response = client.post(
        "/api/settings",
        json=payload,
        headers={"X-Settings-Password": SETTINGS_PASSWORD},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"

    # Verify the settings were actually stored
    get_response = client.get("/api/settings")
    get_data = get_response.get_json()
    assert get_data["fire_department_name"] == "Test Feuerwehr"


def test_post_settings_unauthorized(client) -> None:
    """POST /api/settings without or with wrong password should return 401."""
    # No password
    response = client.post("/api/settings", json={"fire_department_name": "Hacker"})
    assert response.status_code == 401
    assert "error" in response.get_json()

    # Wrong password
    response = client.post(
        "/api/settings",
        json={"fire_department_name": "Hacker"},
        headers={"X-Settings-Password": "wrong-password"},
    )
    assert response.status_code == 401
    assert "error" in response.get_json()


def test_post_settings_invalid_coordinates(client) -> None:
    """POST /api/settings with default_latitude=999 should return 400."""
    response = client.post(
        "/api/settings",
        json={
            "fire_department_name": "Test",
            "default_latitude": 999,
            "default_longitude": 9.0,
        },
        headers={"X-Settings-Password": SETTINGS_PASSWORD},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data


# ---------------------------------------------------------------------------
# GET /api/alarm/participants – incident_number validation (SEC-3)
# ---------------------------------------------------------------------------


def test_api_participants_invalid_incident_number_returns_400(client) -> None:
    """GET /api/alarm/participants with special chars incident_number should return 400."""
    response = client.get("/api/alarm/participants/bad!chars")

    assert response.status_code == 400
    data = response.get_json()
    assert data["error"] == "Invalid incident number"


def test_api_participants_too_long_incident_number_returns_400(client) -> None:
    """GET /api/alarm/participants with overly long incident_number should return 400."""
    long_number = "A" * 51
    response = client.get(f"/api/alarm/participants/{long_number}")

    assert response.status_code == 400
    data = response.get_json()
    assert data["error"] == "Invalid incident number"


def test_api_participants_valid_incident_number_without_messenger(client) -> None:
    """GET /api/alarm/participants with valid incident_number but no messenger returns 503."""
    response = client.get("/api/alarm/participants/12345")

    assert response.status_code == 503
