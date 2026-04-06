"""Tests for the alarm messenger integration."""

from __future__ import annotations

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

    @patch("alarm_dashboard.messenger.requests.get")
    def test_get_participants_success(self, mock_get, messenger_config):
        lookup_response = Mock()
        lookup_response.status_code = 200
        lookup_response.json.return_value = {
            "data": [{"id": "emergency-uuid-123"}],
            "pagination": {"page": 1, "limit": 50, "total": 1, "totalPages": 1},
        }

        participants_response = Mock()
        participants_response.status_code = 200
        participants_response.json.return_value = {
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
        mock_get.side_effect = [lookup_response, participants_response]

        messenger = AlarmMessenger(messenger_config)
        participants = messenger.get_participants("12345")

        assert participants is not None
        assert len(participants) == 2
        assert participants[0]["responder"]["firstName"] == "Max"
        assert participants[0]["responder"]["leadershipRole"] == "groupLeader"
        assert participants[1]["responder"]["firstName"] == "Anna"

        assert mock_get.call_count == 2
        lookup_call = mock_get.call_args_list[0]
        assert lookup_call[0][0] == "https://messenger.example.com/api/emergencies"
        assert lookup_call[1]["params"] == {"emergencyNumber": "12345"}
        assert lookup_call[1]["headers"]["X-API-Key"] == "test-api-key-123"

        participants_call = mock_get.call_args_list[1]
        assert (
            participants_call[0][0]
            == "https://messenger.example.com/api/emergencies/emergency-uuid-123/participants"
        )
        assert participants_call[1]["headers"]["X-API-Key"] == "test-api-key-123"

    @patch("alarm_dashboard.messenger.requests.get")
    def test_get_participants_not_found(self, mock_get, messenger_config):
        lookup_response = Mock()
        lookup_response.status_code = 200
        lookup_response.json.return_value = {
            "data": [],
            "pagination": {"page": 1, "limit": 50, "total": 0, "totalPages": 0},
        }
        mock_get.return_value = lookup_response

        messenger = AlarmMessenger(messenger_config)
        participants = messenger.get_participants("99999")

        assert participants is None

    @patch("alarm_dashboard.messenger.requests.get")
    def test_get_participants_lookup_401_returns_none(self, mock_get, messenger_config):
        lookup_response = Mock()
        lookup_response.status_code = 401
        mock_get.return_value = lookup_response

        messenger = AlarmMessenger(messenger_config)
        participants = messenger.get_participants("12345")

        assert participants is None
        mock_get.assert_called_once()

    @patch("alarm_dashboard.messenger.requests.get")
    def test_get_participants_unexpected_response_format(self, mock_get, messenger_config):
        lookup_response = Mock()
        lookup_response.status_code = 200
        lookup_response.json.return_value = "unexpected string"
        mock_get.return_value = lookup_response

        messenger = AlarmMessenger(messenger_config)
        with patch("alarm_dashboard.messenger.LOGGER") as mock_logger:
            participants = messenger.get_participants("12345")

        assert participants is None
        mock_logger.error.assert_called_once_with(
            "Unexpected emergency lookup response format: %s",
            "str",
        )

    @patch("alarm_dashboard.messenger.requests.get")
    def test_get_participants_list_response_forward_compatible(self, mock_get, messenger_config):
        lookup_response = Mock()
        lookup_response.status_code = 200
        lookup_response.json.return_value = [{"id": "emergency-uuid-456"}]

        participants_response = Mock()
        participants_response.status_code = 200
        participants_response.json.return_value = {
            "emergencyId": "emergency-uuid-456",
            "totalParticipants": 1,
            "participants": [
                {
                    "id": "response-1",
                    "deviceId": "device-1",
                    "platform": "android",
                    "respondedAt": "2024-12-08T14:00:00.000Z",
                    "responder": {
                        "firstName": "Max",
                        "lastName": "Mustermann",
                        "qualifications": {"machinist": True, "agt": False, "paramedic": False},
                        "leadershipRole": "none",
                    },
                }
            ],
        }
        mock_get.side_effect = [lookup_response, participants_response]

        messenger = AlarmMessenger(messenger_config)
        participants = messenger.get_participants("12345")

        assert participants is not None
        assert len(participants) == 1

    @patch("alarm_dashboard.messenger.requests.get")
    def test_get_participants_lookup_request_error(self, mock_get, messenger_config):
        mock_get.side_effect = requests.exceptions.RequestException("Network error")

        messenger = AlarmMessenger(messenger_config)
        participants = messenger.get_participants("12345")

        assert participants is None

    @patch("alarm_dashboard.messenger.requests.get")
    def test_get_participants_request_error(self, mock_get, messenger_config):
        lookup_response = Mock()
        lookup_response.status_code = 200
        lookup_response.json.return_value = {
            "data": [{"id": "emergency-uuid-123"}],
            "pagination": {"page": 1, "limit": 50, "total": 1, "totalPages": 1},
        }

        mock_get.side_effect = [
            lookup_response,
            requests.exceptions.RequestException("Network error"),
        ]

        messenger = AlarmMessenger(messenger_config)
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
