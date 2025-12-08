"""Alarm messenger notification integration.

This module provides functionality to send alarm notifications to an external
alarm messenger server via HTTP API. The integration is activated when the
messenger server URL is configured via environment variables.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

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
        # Cache mapping of incident_number to emergency_id
        self._emergency_id_cache: Dict[str, str] = {}

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

            # Send the notification to the correct endpoint: /api/emergencies
            response = requests.post(
                f"{self.config.server_url}/api/emergencies",
                json=payload,
                headers={
                    "X-API-Key": self.config.api_key,
                    "Content-Type": "application/json",
                },
                timeout=self.config.timeout,
            )

            response.raise_for_status()
            
            # Extract incident number and emergency_id for caching
            alarm = alarm_data.get("alarm", alarm_data)
            incident_number = alarm.get("incident_number")
            
            # Store emergency_id from response for later participant lookups
            emergency_data = response.json()
            if emergency_data and "id" in emergency_data:
                self._emergency_id_cache[incident_number] = emergency_data["id"]
                LOGGER.debug(
                    "Cached emergency_id %s for incident %s",
                    emergency_data["id"],
                    incident_number,
                )
            
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

        The alarm-messenger API expects the following fields:
        - emergencyNumber (required)
        - emergencyDate (required)
        - emergencyKeyword (required)
        - emergencyDescription (required)
        - emergencyLocation (required)
        - groups (optional) - comma-separated group codes

        Args:
            alarm_data: Raw alarm data from the parser

        Returns:
            Formatted payload for the messenger API
        """
        # Extract the alarm object if it's wrapped
        alarm = alarm_data.get("alarm", alarm_data)

        # Map alarm-monitor fields to alarm-messenger API fields
        payload: Dict[str, Any] = {
            "emergencyNumber": alarm.get("incident_number") or "UNKNOWN",
            "emergencyDate": alarm.get("timestamp") or alarm.get("received_at"),
            "emergencyKeyword": alarm.get("keyword") or alarm.get("keyword_primary") or "ALARM",
            "emergencyDescription": alarm.get("description") or alarm.get("diagnosis") or "",
            "emergencyLocation": alarm.get("location") or "",
        }

        # Add optional groups field if present
        # Convert list of groups to comma-separated string if needed
        if alarm.get("dispatch_group_codes"):
            # Use dispatch_group_codes as they represent the TME codes
            codes = alarm.get("dispatch_group_codes")
            if isinstance(codes, list):
                payload["groups"] = ",".join(codes)
            elif isinstance(codes, str):
                payload["groups"] = codes

        return payload

    def get_participants(self, incident_number: str) -> Optional[List[Dict[str, Any]]]:
        """Get participants for an emergency by incident number.

        Args:
            incident_number: The incident number (ENR) from the alarm

        Returns:
            List of participants with responder details, or None if not found/error
        """
        # Get emergency_id from cache
        emergency_id = self._emergency_id_cache.get(incident_number)
        if not emergency_id:
            LOGGER.warning(
                "No emergency_id cached for incident %s, cannot fetch participants",
                incident_number,
            )
            return None

        try:
            # Call the alarm-messenger API to get participants
            response = requests.get(
                f"{self.config.server_url}/api/emergencies/{emergency_id}/participants",
                headers={
                    "X-API-Key": self.config.api_key,
                },
                timeout=self.config.timeout,
            )

            response.raise_for_status()
            data = response.json()

            participants = data.get("participants", [])
            LOGGER.info(
                "Retrieved %d participants for incident %s",
                len(participants),
                incident_number,
            )
            return participants

        except requests.exceptions.Timeout:
            LOGGER.error(
                "Timeout fetching participants from messenger server: %s",
                self.config.server_url,
            )
            return None
        except requests.exceptions.RequestException as exc:
            LOGGER.error("Failed to fetch participants from messenger: %s", exc)
            return None
        except Exception as exc:  # pragma: no cover
            LOGGER.error("Unexpected error fetching participants: %s", exc)
            return None


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
