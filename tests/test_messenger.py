"""Tests for the alarm messenger integration."""

from __future__ import annotations

import json
from unittest.mock import Mock, patch

import pytest
import requests

from alarm_dashboard.messenger import (
    AlarmMessenger,
    AlarmMessengerConfig,
    create_messenger,
)


@pytest.fixture
def messenger_config():
    """Create a test messenger configuration."""
    return AlarmMessengerConfig(
        server_url="https://messenger.example.com",
        api_key="test-api-key-123",
        timeout=10,
    )


@pytest.fixture
def alarm_data():
    """Create sample alarm data for testing."""
    return {
        "alarm": {
            "incident_number": "12345",
            "timestamp": "2024-01-01T12:00:00",
            "keyword": "F3Y – Brand",
            "location": "Musterstraße 1, 12345 Musterstadt",
            "description": "Brand in Wohngebäude",
            "remark": "Mehrere Anrufer",
            "latitude": 51.5,
            "longitude": 9.5,
            "groups": ["LF 1", "DLK 1"],
        },
        "coordinates": {"lat": 51.5, "lon": 9.5},
        "weather": {"temperature": 15},
    }


class TestAlarmMessengerConfig:
    """Tests for AlarmMessengerConfig."""

    def test_config_initialization(self):
        config = AlarmMessengerConfig(
            server_url="https://example.com/",
            api_key="key123",
            timeout=5,
        )
        assert config.server_url == "https://example.com"
        assert config.api_key == "key123"
        assert config.timeout == 5

    def test_config_strips_trailing_slash(self):
        config = AlarmMessengerConfig(
            server_url="https://example.com///",
            api_key="key",
        )
        assert config.server_url == "https://example.com"

    def test_config_default_timeout(self):
        config = AlarmMessengerConfig(
            server_url="https://example.com",
            api_key="key",
        )
        assert config.timeout == 10


class TestAlarmMessenger:
    """Tests for AlarmMessenger."""

    def test_messenger_initialization(self, messenger_config):
        messenger = AlarmMessenger(messenger_config)
        assert messenger.config == messenger_config

    @patch("alarm_dashboard.messenger.requests.post")
    def test_send_alarm_success(self, mock_post, messenger_config, alarm_data):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        messenger = AlarmMessenger(messenger_config)
        result = messenger.send_alarm(alarm_data)

        assert result is True
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        assert call_args[0][0] == "https://messenger.example.com/api/alarm"
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-api-key-123"
        assert call_args[1]["headers"]["Content-Type"] == "application/json"
        assert call_args[1]["timeout"] == 10

        # Verify the payload
        payload = call_args[1]["json"]
        assert payload["incident_number"] == "12345"
        assert payload["keyword"] == "F3Y – Brand"
        assert payload["location"] == "Musterstraße 1, 12345 Musterstadt"

    @patch("alarm_dashboard.messenger.requests.post")
    def test_send_alarm_timeout(self, mock_post, messenger_config, alarm_data):
        mock_post.side_effect = requests.exceptions.Timeout()

        messenger = AlarmMessenger(messenger_config)
        result = messenger.send_alarm(alarm_data)

        assert result is False

    @patch("alarm_dashboard.messenger.requests.post")
    def test_send_alarm_request_error(self, mock_post, messenger_config, alarm_data):
        mock_post.side_effect = requests.exceptions.RequestException("Connection error")

        messenger = AlarmMessenger(messenger_config)
        result = messenger.send_alarm(alarm_data)

        assert result is False

    @patch("alarm_dashboard.messenger.requests.post")
    def test_send_alarm_http_error(self, mock_post, messenger_config, alarm_data):
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()
        mock_post.return_value = mock_response

        messenger = AlarmMessenger(messenger_config)
        result = messenger.send_alarm(alarm_data)

        assert result is False

    def test_send_alarm_empty_data(self, messenger_config):
        messenger = AlarmMessenger(messenger_config)
        result = messenger.send_alarm({})

        assert result is False

    def test_prepare_payload_with_coordinates(self, messenger_config, alarm_data):
        messenger = AlarmMessenger(messenger_config)
        payload = messenger._prepare_payload(alarm_data)

        assert payload["incident_number"] == "12345"
        assert payload["keyword"] == "F3Y – Brand"
        assert payload["location"] == "Musterstraße 1, 12345 Musterstadt"
        assert payload["description"] == "Brand in Wohngebäude"
        assert payload["remark"] == "Mehrere Anrufer"
        assert payload["groups"] == ["LF 1", "DLK 1"]
        assert payload["coordinates"] == {"lat": 51.5, "lon": 9.5}

    def test_prepare_payload_without_wrapped_alarm(self, messenger_config):
        messenger = AlarmMessenger(messenger_config)
        # Test with unwrapped alarm data
        alarm_data = {
            "incident_number": "67890",
            "timestamp": "2024-01-02T14:00:00",
            "keyword": "H1",
            "location": "Test Location",
            "latitude": 52.0,
            "longitude": 10.0,
        }
        payload = messenger._prepare_payload(alarm_data)

        assert payload["incident_number"] == "67890"
        assert payload["keyword"] == "H1"
        assert payload["coordinates"] == {"lat": 52.0, "lon": 10.0}

    def test_prepare_payload_minimal_data(self, messenger_config):
        messenger = AlarmMessenger(messenger_config)
        alarm_data = {
            "alarm": {
                "incident_number": "11111",
                "keyword": "Test",
            }
        }
        payload = messenger._prepare_payload(alarm_data)

        assert payload["incident_number"] == "11111"
        assert payload["keyword"] == "Test"
        assert payload["coordinates"] is None
        assert "remark" not in payload
        assert "groups" not in payload


class TestCreateMessenger:
    """Tests for create_messenger factory function."""

    def test_create_messenger_with_valid_config(self):
        messenger = create_messenger(
            "https://messenger.example.com",
            "api-key-123",
        )

        assert messenger is not None
        assert isinstance(messenger, AlarmMessenger)
        assert messenger.config.server_url == "https://messenger.example.com"
        assert messenger.config.api_key == "api-key-123"

    def test_create_messenger_without_server_url(self):
        messenger = create_messenger(None, "api-key-123")
        assert messenger is None

    def test_create_messenger_without_api_key(self):
        messenger = create_messenger("https://messenger.example.com", None)
        assert messenger is None

    def test_create_messenger_with_empty_strings(self):
        messenger = create_messenger("", "")
        assert messenger is None
