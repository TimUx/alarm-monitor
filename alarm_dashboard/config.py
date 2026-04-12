"""Application configuration utilities.

This module centralises configuration handling for the alarm dashboard
application. Configuration is primarily sourced from environment
variables so deployments can inject secrets (such as API keys)
without committing them to the repository.
"""

from __future__ import annotations

import os
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, cast

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional dependency fallback
    def load_dotenv(*_args, **_kwargs):  # type: ignore[override]
        """Fallback shim if python-dotenv is not installed."""

        return False


@dataclass
class AppConfig:
    """Top level configuration container."""

    api_key: Optional[str]
    activation_groups: List[str] = field(default_factory=list)
    display_duration_minutes: int = 30
    fire_department_name: str = "Alarm-Monitor"
    nominatim_base_url: str = "https://nominatim.openstreetmap.org/search"
    weather_base_url: str = "https://api.open-meteo.com/v1/forecast"
    weather_params: str = "current_weather=true&hourly=precipitation,precipitation_probability,rain,showers,snowfall&forecast_days=1"
    default_latitude: Optional[float] = None
    default_longitude: Optional[float] = None
    default_location_name: Optional[str] = None
    history_file: Optional[str] = None
    settings_file: Optional[str] = None
    ors_api_key: Optional[str] = None
    app_version: str = "dev-main"
    app_version_url: Optional[str] = None
    messenger_server_url: Optional[str] = None
    messenger_api_key: Optional[str] = None
    settings_password: Optional[str] = None
    calendar_urls: List[str] = field(default_factory=list)


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

    # API key for receiving alarms from alarm-mail service
    api_key = _get_env("API_KEY") or None
    if not api_key:
        LOGGER.warning(
            "API_KEY not set. The /api/alarm endpoint will reject all requests. "
            "Set ALARM_DASHBOARD_API_KEY to enable API-based alarm reception."
        )
    elif api_key == "change-me-to-random-api-key":
        LOGGER.critical(
            "API_KEY is set to the example default value. Please change it immediately."
        )

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
    settings_file = _get_env("SETTINGS_FILE") or None

    def _validate_path(path_str: str, env_name: str) -> None:
        from pathlib import Path as _Path
        if not path_str.startswith("/"):
            raise MissingConfiguration(
                f"{ENV_PREFIX}{env_name} must be an absolute path (got: {path_str!r})"
            )
        if ".." in _Path(path_str).parts:
            raise MissingConfiguration(
                f"{ENV_PREFIX}{env_name} must not contain '..' components (got: {path_str!r})"
            )
        resolved = os.path.realpath(path_str)
        allowed_base = os.path.realpath("/app/instance")
        if not resolved.startswith(allowed_base + os.sep):
            raise MissingConfiguration(
                f"{ENV_PREFIX}{env_name} path escapes allowed directory: {resolved!r}"
            )

    if history_file:
        _validate_path(history_file, "HISTORY_FILE")
    if settings_file:
        _validate_path(settings_file, "SETTINGS_FILE")
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
        _get_env("FIRE_DEPARTMENT_NAME", default="Alarm-Monitor")
        or "Alarm-Monitor"
    )

    ors_api_key = _get_env("ORS_API_KEY") or None

    settings_password = _get_env("SETTINGS_PASSWORD") or None
    if not settings_password:
        LOGGER.critical(
            "ALARM_DASHBOARD_SETTINGS_PASSWORD is not set — settings page is unprotected!"
        )

    # Calendar URLs (newline or comma-separated iCal URLs)
    calendar_urls_raw = _get_env("CALENDAR_URLS") or None
    calendar_urls: List[str] = []
    if calendar_urls_raw:
        for item in re.split(r"[\n,]+", calendar_urls_raw):
            item = item.strip()
            if item:
                calendar_urls.append(item)

    # Alarm messenger configuration
    messenger_server_url = _get_env("MESSENGER_SERVER_URL") or None
    messenger_api_key = _get_env("MESSENGER_API_KEY") or None

    # Validate messenger configuration - both URL and API key are required
    if messenger_server_url and not messenger_api_key:
        LOGGER.warning(
            "MESSENGER_SERVER_URL is set but MESSENGER_API_KEY is missing. "
            "Alarm messenger integration will be disabled."
        )
        # Clear both to maintain consistency
        messenger_server_url = None
        messenger_api_key = None
    elif messenger_server_url and messenger_api_key:
        LOGGER.info(
            "Alarm messenger integration enabled: %s", messenger_server_url
        )

    default_version = "dev-main"
    app_version = _get_env("APP_VERSION") or default_version
    app_version_url = _get_env("APP_VERSION_URL") or None
    if not app_version_url:
        if app_version and app_version != default_version:
            app_version_url = (
                "https://github.com/feuerwehr-willingshausen/alarm-dashboard/"
                f"releases/tag/{app_version}"
            )
        else:
            app_version_url = (
                "https://github.com/feuerwehr-willingshausen/alarm-dashboard/"
                "releases"
            )

    return AppConfig(
        api_key=api_key,
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
        settings_file=settings_file,
        ors_api_key=ors_api_key,
        app_version=app_version,
        app_version_url=app_version_url,
        messenger_server_url=messenger_server_url,
        messenger_api_key=messenger_api_key,
        settings_password=settings_password,
        calendar_urls=calendar_urls,
    )


__all__ = [
    "AppConfig",
    "MissingConfiguration",
    "load_config",
]
