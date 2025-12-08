"""Alarm messenger integration for participant responses.

This module provides functionality to retrieve participant responses from an
external alarm messenger server. The alarm messenger is notified of emergencies
by the alarm-mail service, and this module polls for participant confirmations.
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
    """Client for retrieving participant responses from alarm messenger server."""

    def __init__(self, config: AlarmMessengerConfig):
        """Initialize the alarm messenger client.

        Args:
            config: Configuration for the messenger service
        """
        self.config = config
        # Cache mapping of incident_number to emergency_id
        self._emergency_id_cache: Dict[str, str] = {}

    def register_emergency(self, incident_number: str, emergency_id: str) -> None:
        """Register an emergency_id for an incident number.

        This allows participant lookups by incident number.
        Typically called when an alarm is received from the alarm-mail service.

        Args:
            incident_number: The incident number (ENR) from the alarm
            emergency_id: The emergency ID from alarm-messenger
        """
        if incident_number and emergency_id:
            self._emergency_id_cache[incident_number] = emergency_id
            LOGGER.debug(
                "Registered emergency_id %s for incident %s",
                emergency_id,
                incident_number,
            )

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
