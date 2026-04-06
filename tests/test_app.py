"""Tests for the Flask application factory (API endpoint architecture)."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from alarm_dashboard.config import AppConfig
from alarm_dashboard import app as app_module
from alarm_dashboard.app import generate_csrf_token


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
    """An alarm payload missing incident_number must be rejected with HTTP 400."""
    alarm_data = {"keyword": "F3Y", "location": "Somewhere"}

    response = client.post(
        "/api/alarm",
        json=alarm_data,
        headers={"X-API-Key": API_KEY},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert "incident_number is required" in data["error"]
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
        headers={
            "X-Settings-Password": SETTINGS_PASSWORD,
            "X-CSRF-Token": generate_csrf_token(SETTINGS_PASSWORD),
        },
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
        headers={
            "X-Settings-Password": SETTINGS_PASSWORD,
            "X-CSRF-Token": generate_csrf_token(SETTINGS_PASSWORD),
        },
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


# ---------------------------------------------------------------------------
# GET /api/stream – Server-Sent Events
# ---------------------------------------------------------------------------


def test_api_stream_content_type(client) -> None:
    """GET /api/stream should return 200 with text/event-stream content type."""
    resp = client.get("/api/stream")
    # Access headers without consuming the streaming body
    assert resp.status_code == 200
    assert "text/event-stream" in resp.content_type


def test_post_alarm_notifies_sse_subscribers(client, flask_app) -> None:
    """Posting a new alarm should set all registered SSE subscriber events."""
    evt = threading.Event()
    flask_app.config["SSE_SUBSCRIBERS"].append(evt)
    try:
        alarm_data = {"incident_number": "SSE-001", "keyword": "F3Y"}
        client.post("/api/alarm", json=alarm_data, headers={"X-API-Key": API_KEY})
        assert evt.is_set(), "SSE subscriber event was not set after alarm was received"
    finally:
        try:
            flask_app.config["SSE_SUBSCRIBERS"].remove(evt)
        except ValueError:
            pass


def test_sse_subscriber_not_notified_for_dropped_alarm(client, flask_app) -> None:
    """An alarm silently dropped by process_alarm (missing incident_number) must not notify subscribers."""
    evt = threading.Event()
    flask_app.config["SSE_SUBSCRIBERS"].append(evt)
    try:
        # Alarm without incident_number is silently dropped by process_alarm
        client.post(
            "/api/alarm",
            json={"keyword": "F3Y"},
            headers={"X-API-Key": API_KEY},
        )
        assert not evt.is_set(), "SSE subscriber was notified for a dropped alarm"
    finally:
        try:
            flask_app.config["SSE_SUBSCRIBERS"].remove(evt)
        except ValueError:
            pass


# ---------------------------------------------------------------------------
# Part 2a – SSE max concurrent connections
# ---------------------------------------------------------------------------


def test_api_stream_rejects_when_max_connections_reached(flask_app) -> None:
    """GET /api/stream should return 503 when 20 concurrent connections are already open."""
    mock_events = [threading.Event() for _ in range(20)]
    flask_app.config["SSE_SUBSCRIBERS"].extend(mock_events)
    try:
        with flask_app.test_client() as c:
            r = c.get("/api/stream")
            assert r.status_code == 503
            assert b"Too many concurrent streams" in r.data
    finally:
        for evt in mock_events:
            try:
                flask_app.config["SSE_SUBSCRIBERS"].remove(evt)
            except ValueError:
                pass


# ---------------------------------------------------------------------------
# Part 2b – Alarm payload validation
# ---------------------------------------------------------------------------


def test_post_alarm_with_oversized_keyword_returns_400(client) -> None:
    """POST /api/alarm with keyword > 500 chars should return 400."""
    response = client.post(
        "/api/alarm",
        json={"incident_number": "12345", "keyword": "X" * 501},
        headers={"X-API-Key": API_KEY},
    )
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_post_alarm_with_invalid_incident_number_chars_returns_400(client) -> None:
    """POST /api/alarm with incident_number containing invalid chars should return 400."""
    response = client.post(
        "/api/alarm",
        json={"incident_number": "INVALID!@#$"},
        headers={"X-API-Key": API_KEY},
    )
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_post_alarm_with_out_of_range_latitude_returns_400(client) -> None:
    """POST /api/alarm with latitude > 90 should return 400."""
    response = client.post(
        "/api/alarm",
        json={"incident_number": "12345", "latitude": 91.0, "longitude": 9.0},
        headers={"X-API-Key": API_KEY},
    )
    assert response.status_code == 400
    assert "error" in response.get_json()


# ---------------------------------------------------------------------------
# Part 2d – CSRF protection
# ---------------------------------------------------------------------------


def test_post_settings_rejects_missing_csrf_token(client) -> None:
    """POST /api/settings without X-CSRF-Token should return 403."""
    response = client.post(
        "/api/settings",
        json={"fire_department_name": "Test"},
        headers={"X-Settings-Password": SETTINGS_PASSWORD},
    )
    assert response.status_code == 403
    assert "error" in response.get_json()


def test_post_settings_rejects_invalid_csrf_token(client) -> None:
    """POST /api/settings with wrong X-CSRF-Token should return 403."""
    response = client.post(
        "/api/settings",
        json={"fire_department_name": "Test"},
        headers={
            "X-Settings-Password": SETTINGS_PASSWORD,
            "X-CSRF-Token": "invalid-token",
        },
    )
    assert response.status_code == 403
    assert "error" in response.get_json()


def test_post_settings_accepts_valid_csrf_token(client) -> None:
    """POST /api/settings with valid X-CSRF-Token should return 200."""
    response = client.post(
        "/api/settings",
        json={"fire_department_name": "Valid FW"},
        headers={
            "X-Settings-Password": SETTINGS_PASSWORD,
            "X-CSRF-Token": generate_csrf_token(SETTINGS_PASSWORD),
        },
    )
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Part 3a – SSE resource leak fix
# ---------------------------------------------------------------------------


def test_sse_subscriber_removed_on_generator_close(flask_app) -> None:
    """Closing the generate() generator must remove the subscriber from _subscribers."""
    with flask_app.test_client() as c:
        with c.get("/api/stream") as resp:
            assert resp.status_code == 200
            first_chunk = next(iter(resp.response), b"")
            assert b"connected" in first_chunk

        assert len(flask_app.config["SSE_SUBSCRIBERS"]) == 0


# ---------------------------------------------------------------------------
# Part 5d – Prometheus metrics
# ---------------------------------------------------------------------------


def test_metrics_endpoint_requires_token(client) -> None:
    """GET /api/metrics without token should return 503 if unconfigured."""
    import os
    original = os.environ.get("ALARM_DASHBOARD_METRICS_TOKEN")
    try:
        os.environ.pop("ALARM_DASHBOARD_METRICS_TOKEN", None)
        response = client.get("/api/metrics")
        assert response.status_code == 503
    finally:
        if original is not None:
            os.environ["ALARM_DASHBOARD_METRICS_TOKEN"] = original


def test_metrics_endpoint_returns_prometheus_format(client) -> None:
    """GET /api/metrics with valid token should return Prometheus plain text."""
    import os
    token = "test-metrics-token-123"
    os.environ["ALARM_DASHBOARD_METRICS_TOKEN"] = token
    try:
        response = client.get(
            "/api/metrics",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert b"alarm_dashboard_alarms_received_total" in response.data
        assert b"alarm_dashboard_sse_active_connections" in response.data
        assert b"alarm_dashboard_history_size" in response.data
    finally:
        os.environ.pop("ALARM_DASHBOARD_METRICS_TOKEN", None)


# ---------------------------------------------------------------------------
# View route tests (coverage for routes/views.py)
# ---------------------------------------------------------------------------


def test_dashboard_page_returns_200(client) -> None:
    """GET / should return 200 with dashboard HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"dashboard" in response.data.lower() or b"feuerwehr" in response.data.lower()


def test_history_page_returns_200(client) -> None:
    """GET /history should return 200 with history HTML."""
    response = client.get("/history")
    assert response.status_code == 200
    assert b"historie" in response.data.lower() or b"history" in response.data.lower()


def test_mobile_page_returns_200(client) -> None:
    """GET /mobile should return 200 with mobile HTML."""
    response = client.get("/mobile")
    assert response.status_code == 200


def test_navigation_page_returns_200(client) -> None:
    """GET /navigation should return 200 with navigation HTML."""
    response = client.get("/navigation")
    assert response.status_code == 200


def test_settings_page_returns_200(client) -> None:
    """GET /settings should return 200 with settings HTML."""
    response = client.get("/settings")
    assert response.status_code == 200
    assert b"settings" in response.data.lower() or b"einstellungen" in response.data.lower()


def test_health_returns_200(client) -> None:
    """GET /health should return 200 with ok status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Additional API coverage tests
# ---------------------------------------------------------------------------


def test_api_history_with_offset(client, flask_app) -> None:
    """GET /api/history?offset=0 should return history payload."""
    response = client.get("/api/history?limit=10&offset=0")
    assert response.status_code == 200
    data = response.get_json()
    assert "history" in data


def test_api_settings_returns_settings(client) -> None:
    """GET /api/settings should return current settings."""
    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.get_json()
    assert "fire_department_name" in data


def test_api_participants_invalid_incident_number(client) -> None:
    """GET /api/alarm/participants/<bad> should return 400."""
    response = client.get("/api/alarm/participants/invalid!@#")
    assert response.status_code == 400


def test_api_participants_no_messenger(client) -> None:
    """GET /api/alarm/participants/<valid> should return 503 when messenger not configured."""
    response = client.get("/api/alarm/participants/123-VALID")
    assert response.status_code == 503


def test_api_route_returns_503_when_not_configured(client) -> None:
    """GET /api/route should return 503 when ORS API key is not configured."""
    response = client.get("/api/route?start_lat=50&start_lon=9&end_lat=51&end_lon=10")
    assert response.status_code == 503


def test_api_metrics_unauthorized(client) -> None:
    """GET /api/metrics with wrong token should return 401."""
    import os
    token = "correct-token-abc"
    os.environ["ALARM_DASHBOARD_METRICS_TOKEN"] = token
    try:
        response = client.get(
            "/api/metrics",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert response.status_code == 401
    finally:
        os.environ.pop("ALARM_DASHBOARD_METRICS_TOKEN", None)


def test_post_alarm_unauthorized(client) -> None:
    """POST /api/alarm with wrong API key should return 401."""
    response = client.post(
        "/api/alarm",
        json={"incident_number": "TEST-001"},
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 401


def test_post_alarm_empty_body(client) -> None:
    """POST /api/alarm with no body should return 400."""
    response = client.post(
        "/api/alarm",
        headers={"X-API-Key": API_KEY},
        content_type="application/json",
        data="",
    )
    assert response.status_code == 400


def test_post_settings_unauthorized(client) -> None:
    """POST /api/settings with wrong password should return 401."""
    response = client.post(
        "/api/settings",
        json={"fire_department_name": "Test"},
        headers={"X-Settings-Password": "wrong-password"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Alarm processor validation tests (for alarm_processor.py coverage)
# ---------------------------------------------------------------------------


def test_post_alarm_with_empty_incident_number_returns_400(client) -> None:
    """POST /api/alarm with empty incident_number should return 400."""
    response = client.post(
        "/api/alarm",
        json={"incident_number": ""},
        headers={"X-API-Key": API_KEY},
    )
    assert response.status_code == 400


def test_post_alarm_with_oversized_subject_returns_400(client) -> None:
    """POST /api/alarm with subject > 500 chars should return 400."""
    response = client.post(
        "/api/alarm",
        json={"incident_number": "TEST-001", "subject": "S" * 501},
        headers={"X-API-Key": API_KEY},
    )
    assert response.status_code == 400


def test_post_alarm_with_oversized_location_returns_400(client) -> None:
    """POST /api/alarm with location > 500 chars should return 400."""
    response = client.post(
        "/api/alarm",
        json={"incident_number": "TEST-001", "location": "L" * 501},
        headers={"X-API-Key": API_KEY},
    )
    assert response.status_code == 400


def test_post_alarm_with_out_of_range_longitude_returns_400(client) -> None:
    """POST /api/alarm with longitude < -180 should return 400."""
    response = client.post(
        "/api/alarm",
        json={"incident_number": "12345", "latitude": 50.0, "longitude": -181.0},
        headers={"X-API-Key": API_KEY},
    )
    assert response.status_code == 400


def test_post_alarm_with_invalid_groups_list_item_returns_400(client) -> None:
    """POST /api/alarm with a groups item > 200 chars should return 400."""
    response = client.post(
        "/api/alarm",
        json={"incident_number": "12345", "groups": ["X" * 201]},
        headers={"X-API-Key": API_KEY},
    )
    assert response.status_code == 400
