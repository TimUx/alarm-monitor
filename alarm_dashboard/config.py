"""Application configuration utilities.

This module centralises configuration handling for the alarm dashboard
application. Configuration is primarily sourced from environment
variables so deployments can inject secrets (such as IMAP credentials)
without committing them to the repository.
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from typing import List, Optional, cast

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional dependency fallback
    def load_dotenv(*_args, **_kwargs):  # type: ignore[override]
        """Fallback shim if python-dotenv is not installed."""

        return False


@dataclass
class MailConfig:
    """IMAP mail server configuration."""

    host: str
    username: str
    password: str
    mailbox: str = "INBOX"
    port: int = 993
    use_ssl: bool = True
    search_criteria: str = "UNSEEN"


@dataclass
class AppConfig:
    """Top level configuration container."""

    mail: Optional[MailConfig]
    poll_interval: int = 60
    activation_groups: List[str] = field(default_factory=list)
    display_duration_minutes: int = 30
    fire_department_name: str = "Willingshausen"
    nominatim_base_url: str = "https://nominatim.openstreetmap.org/search"
    weather_base_url: str = "https://api.open-meteo.com/v1/forecast"
    weather_params: str = "current_weather=true"
    default_latitude: Optional[float] = None
    default_longitude: Optional[float] = None
    default_location_name: Optional[str] = None
    history_file: Optional[str] = None


class MissingConfiguration(RuntimeError):
    """Raised when a required environment variable is missing."""


ENV_PREFIX = "ALARM_DASHBOARD_"

LOGGER = logging.getLogger(__name__)


# Load environment variables from a local ``.env`` file if present.  This
# enables deployments to define configuration without exporting every
# variable in the shell environment.
load_dotenv()


def _get_env(name: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    """Fetch an environment variable with optional default and validation."""

    value = os.environ.get(f"{ENV_PREFIX}{name}")
    if value is None:
        if required and default is None:
            raise MissingConfiguration(
                f"Missing required environment variable: {ENV_PREFIX}{name}"
            )
        value = default
    return value


def load_config() -> AppConfig:
    """Load application configuration from environment variables."""

    host = _get_env("IMAP_HOST")
    username = _get_env("IMAP_USERNAME")
    password = _get_env("IMAP_PASSWORD")

    mail: Optional[MailConfig]
    if host and username and password:
        mail = MailConfig(
            host=cast(str, host),
            username=cast(str, username),
            password=cast(str, password),
            mailbox=_get_env("IMAP_MAILBOX", default="INBOX") or "INBOX",
            port=int(_get_env("IMAP_PORT", default="993") or "993"),
            use_ssl=(
                _get_env("IMAP_USE_SSL", default="true") or "true"
            ).lower()
            != "false",
            search_criteria=_get_env("IMAP_SEARCH", default="UNSEEN") or "UNSEEN",
        )
    else:
        missing = [
            name
            for name, value in (
                ("IMAP_HOST", host),
                ("IMAP_USERNAME", username),
                ("IMAP_PASSWORD", password),
            )
            if not value
        ]
        LOGGER.warning(
            "IMAP configuration incomplete (missing: %s). "
            "Mail fetching will be disabled.",
            ", ".join(missing) or "unknown",
        )
        mail = None

    poll_interval = int(_get_env("POLL_INTERVAL", default="60") or "60")
    activation_raw = _get_env("GRUPPEN")
    activation_groups: List[str] = []
    if activation_raw:
        activation_groups = [
            item.strip().upper()
            for item in activation_raw.split(",")
            if item.strip()
        ]

    display_duration_minutes = int(
        _get_env("DISPLAY_DURATION_MINUTES", default="30") or "30"
    )

    nominatim_base_url = _get_env(
        "NOMINATIM_URL", default="https://nominatim.openstreetmap.org/search"
    ) or "https://nominatim.openstreetmap.org/search"
    weather_base_url = (
        _get_env("WEATHER_URL", default="https://api.open-meteo.com/v1/forecast")
        or "https://api.open-meteo.com/v1/forecast"
    )
    weather_params = (
        _get_env(
            "WEATHER_PARAMS",
            default=(
                "current_weather=true&hourly=precipitation,precipitation_probability,rain,showers,snowfall"
                "&forecast_days=1"
            ),
        )
        or "current_weather=true&hourly=precipitation,precipitation_probability,rain,showers,snowfall&forecast_days=1"
    )

    default_latitude_raw = _get_env("DEFAULT_LATITUDE") or None
    default_longitude_raw = _get_env("DEFAULT_LONGITUDE") or None
    default_location_name = _get_env("DEFAULT_LOCATION_NAME") or None
    history_file = _get_env("HISTORY_FILE") or None
    default_latitude_float: Optional[float] = None
    default_longitude_float: Optional[float] = None
    if default_latitude_raw is not None and default_longitude_raw is not None:
        try:
            default_latitude_float = float(default_latitude_raw)
            default_longitude_float = float(default_longitude_raw)
        except ValueError as exc:
            raise MissingConfiguration(
                "DEFAULT_LATITUDE and DEFAULT_LONGITUDE must be numeric"
            ) from exc

    fire_department_name = (
        _get_env("FIRE_DEPARTMENT_NAME", default="Willingshausen")
        or "Willingshausen"
    )

    return AppConfig(
        mail=mail,
        poll_interval=poll_interval,
        nominatim_base_url=nominatim_base_url,
        activation_groups=activation_groups,
        display_duration_minutes=display_duration_minutes,
        fire_department_name=fire_department_name,
        weather_base_url=weather_base_url,
        weather_params=weather_params,
        default_latitude=default_latitude_float,
        default_longitude=default_longitude_float,
        default_location_name=default_location_name,
        history_file=history_file,
        ors_api_key=ors_api_key,
    )


__all__ = [
    "AppConfig",
    "MailConfig",
    "MissingConfiguration",
    "load_config",
]
