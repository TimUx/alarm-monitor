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
        mock_response.json.return_value = {"id": "emergency-uuid-123"}
        mock_post.return_value = mock_response

        messenger = AlarmMessenger(messenger_config)
        result = messenger.send_alarm(alarm_data)

        assert result is True
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        assert call_args[0][0] == "https://messenger.example.com/api/emergencies"
        assert call_args[1]["headers"]["X-API-Key"] == "test-api-key-123"
        assert call_args[1]["headers"]["Content-Type"] == "application/json"
        assert call_args[1]["timeout"] == 10

        # Verify the payload matches alarm-messenger API structure
        payload = call_args[1]["json"]
        assert payload["emergencyNumber"] == "12345"
        assert payload["emergencyKeyword"] == "F3Y – Brand"
        assert payload["emergencyLocation"] == "Musterstraße 1, 12345 Musterstadt"
        
        # Verify emergency_id was cached
        assert messenger._emergency_id_cache.get("12345") == "emergency-uuid-123"

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

        # Verify alarm-messenger API field names
        assert payload["emergencyNumber"] == "12345"
        assert payload["emergencyKeyword"] == "F3Y – Brand"
        assert payload["emergencyLocation"] == "Musterstraße 1, 12345 Musterstadt"
        assert payload["emergencyDescription"] == "Brand in Wohngebäude"
        assert payload["emergencyDate"] == "2024-01-01T12:00:00"
        # groups should be comma-separated string if present
        assert "groups" not in payload or isinstance(payload.get("groups"), str)

    def test_prepare_payload_without_wrapped_alarm(self, messenger_config):
        messenger = AlarmMessenger(messenger_config)
        # Test with unwrapped alarm data
        alarm_data = {
            "incident_number": "67890",
            "timestamp": "2024-01-02T14:00:00",
            "keyword": "H1",
            "location": "Test Location",
            "description": "Test description",
        }
        payload = messenger._prepare_payload(alarm_data)

        assert payload["emergencyNumber"] == "67890"
        assert payload["emergencyKeyword"] == "H1"
        assert payload["emergencyLocation"] == "Test Location"
        assert payload["emergencyDescription"] == "Test description"

    def test_prepare_payload_minimal_data(self, messenger_config):
        messenger = AlarmMessenger(messenger_config)
        alarm_data = {
            "alarm": {
                "incident_number": "11111",
                "keyword": "Test",
            }
        }
        payload = messenger._prepare_payload(alarm_data)

        assert payload["emergencyNumber"] == "11111"
        assert payload["emergencyKeyword"] == "Test"
        assert payload["emergencyLocation"] == ""
        assert payload["emergencyDescription"] == ""
        # groups only included if dispatch_group_codes present
        assert "groups" not in payload

    def test_prepare_payload_with_dispatch_group_codes(self, messenger_config):
        messenger = AlarmMessenger(messenger_config)
        alarm_data = {
            "alarm": {
                "incident_number": "22222",
                "keyword": "F3Y",
                "location": "Test",
                "description": "Test",
                "timestamp": "2024-01-01T12:00:00",
                "dispatch_group_codes": ["WIL26", "WIL41"],
            }
        }
        payload = messenger._prepare_payload(alarm_data)

        assert payload["emergencyNumber"] == "22222"
        # groups should be comma-separated string
        assert payload["groups"] == "WIL26,WIL41"

    @patch("alarm_dashboard.messenger.requests.get")
    def test_get_participants_success(self, mock_get, messenger_config):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "emergencyId": "emergency-uuid-123",
            "totalParticipants": 2,
            "participants": [
                {
                    "id": "response-1",
                    "deviceId": "device-1",
                    "platform": "android",
                    "respondedAt": "2024-12-08T14:00:00.000Z",
                    "responder": {
                        "firstName": "Max",
                        "lastName": "Mustermann",
                        "qualifications": {
                            "machinist": True,
                            "agt": True,
                            "paramedic": False,
                        },
                        "leadershipRole": "groupLeader",
                    },
                },
                {
                    "id": "response-2",
                    "deviceId": "device-2",
                    "platform": "ios",
                    "respondedAt": "2024-12-08T14:01:00.000Z",
                    "responder": {
                        "firstName": "Anna",
                        "lastName": "Schmidt",
                        "qualifications": {
                            "machinist": False,
                            "agt": False,
                            "paramedic": True,
                        },
                        "leadershipRole": "none",
                    },
                },
            ],
        }
        mock_get.return_value = mock_response

        messenger = AlarmMessenger(messenger_config)
        # Manually set cache entry
        messenger._emergency_id_cache["12345"] = "emergency-uuid-123"

        participants = messenger.get_participants("12345")

        assert participants is not None
        assert len(participants) == 2
        assert participants[0]["responder"]["firstName"] == "Max"
        assert participants[0]["responder"]["leadershipRole"] == "groupLeader"
        assert participants[1]["responder"]["firstName"] == "Anna"

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert (
            call_args[0][0]
            == "https://messenger.example.com/api/emergencies/emergency-uuid-123/participants"
        )
        assert call_args[1]["headers"]["X-API-Key"] == "test-api-key-123"

    def test_get_participants_no_cache(self, messenger_config):
        messenger = AlarmMessenger(messenger_config)
        participants = messenger.get_participants("99999")

        assert participants is None

    @patch("alarm_dashboard.messenger.requests.get")
    def test_get_participants_request_error(self, mock_get, messenger_config):
        mock_get.side_effect = requests.exceptions.RequestException("Network error")

        messenger = AlarmMessenger(messenger_config)
        messenger._emergency_id_cache["12345"] = "emergency-uuid-123"

        participants = messenger.get_participants("12345")

        assert participants is None


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
