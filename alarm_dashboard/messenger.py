"""Alarm messenger notification integration.

This module provides functionality to send alarm notifications to an external
alarm messenger server via HTTP API. The integration is activated when the
messenger server URL is configured via environment variables.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests

LOGGER = logging.getLogger(__name__)


class AlarmMessengerConfig:
    """Configuration for alarm messenger integration."""

    def __init__(self, server_url: str, api_key: str, timeout: int = 10):
        """Initialize messenger configuration.

        Args:
            server_url: Base URL of the alarm messenger server
            api_key: API key or token for authentication
            timeout: Request timeout in seconds (default: 10)
        """
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout


class AlarmMessenger:
    """Client for sending alarm notifications to alarm messenger server."""

    def __init__(self, config: AlarmMessengerConfig):
        """Initialize the alarm messenger client.

        Args:
            config: Configuration for the messenger service
        """
        self.config = config

    def send_alarm(self, alarm_data: Dict[str, Any]) -> bool:
        """Send alarm notification to the messenger server.

        Args:
            alarm_data: Dictionary containing alarm information

        Returns:
            True if notification was sent successfully, False otherwise
        """
        if not alarm_data:
            LOGGER.warning("Cannot send empty alarm data to messenger")
            return False

        try:
            # Prepare the payload for the messenger API
            payload = self._prepare_payload(alarm_data)

            # Send the notification
            response = requests.post(
                f"{self.config.server_url}/api/alarm",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.config.timeout,
            )

            response.raise_for_status()
            
            # Extract incident number for logging (handle both wrapped and unwrapped formats)
            alarm = alarm_data.get("alarm", alarm_data)
            incident_number = alarm.get("incident_number")
            
            LOGGER.info(
                "Successfully sent alarm notification to messenger: incident=%s",
                incident_number,
            )
            return True

        except requests.exceptions.Timeout:
            LOGGER.error(
                "Timeout sending alarm to messenger server: %s",
                self.config.server_url,
            )
            return False
        except requests.exceptions.RequestException as exc:
            LOGGER.error("Failed to send alarm to messenger: %s", exc)
            return False
        except Exception as exc:  # pragma: no cover
            LOGGER.error("Unexpected error sending alarm to messenger: %s", exc)
            return False

    def _prepare_payload(self, alarm_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare the alarm data payload for the messenger API.

        Args:
            alarm_data: Raw alarm data from the parser

        Returns:
            Formatted payload for the messenger API
        """
        # Extract the alarm object if it's wrapped
        alarm = alarm_data.get("alarm", alarm_data)

        # Build a structured payload with the most relevant fields
        payload: Dict[str, Any] = {
            "incident_number": alarm.get("incident_number"),
            "timestamp": alarm.get("timestamp"),
            "keyword": alarm.get("keyword"),
            "location": alarm.get("location"),
            "description": alarm.get("description"),
            "coordinates": None,
        }

        # Add coordinates if available
        if "coordinates" in alarm_data:
            payload["coordinates"] = alarm_data["coordinates"]
        elif alarm.get("latitude") and alarm.get("longitude"):
            payload["coordinates"] = {
                "lat": alarm["latitude"],
                "lon": alarm["longitude"],
            }

        # Add optional fields if present
        if alarm.get("remark"):
            payload["remark"] = alarm["remark"]

        if alarm.get("groups"):
            payload["groups"] = alarm["groups"]

        return payload


def create_messenger(
    server_url: Optional[str], api_key: Optional[str]
) -> Optional[AlarmMessenger]:
    """Create an alarm messenger client if configuration is provided.

    Args:
        server_url: Messenger server URL from configuration
        api_key: API key/token from configuration

    Returns:
        AlarmMessenger instance if both parameters are provided, None otherwise
    """
    if not server_url or not api_key:
        return None

    config = AlarmMessengerConfig(server_url=server_url, api_key=api_key)
    return AlarmMessenger(config)


__all__ = [
    "AlarmMessenger",
    "AlarmMessengerConfig",
    "create_messenger",
]
