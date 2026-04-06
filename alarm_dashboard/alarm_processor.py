"""Alarm processing logic: geocoding, weather lookup, and store updates."""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, Optional, Set

LOGGER = logging.getLogger(__name__)

_INCIDENT_NUMBER_RE = re.compile(r'^[A-Za-z0-9\-_]{1,50}$')

_OPTIONAL_STRING_FIELDS = (
    "keyword", "subject", "location", "diagnosis",
    "remark", "timestamp", "timestamp_display",
)
_OPTIONAL_LIST_FIELDS = (
    "groups", "aao_groups", "dispatch_groups", "dispatch_group_codes",
)


def validate_alarm_payload(alarm: dict) -> None:
    """Validate alarm payload fields.

    incident_number is required and must be 1–50 alphanumeric/dash/underscore chars.
    When other optional fields are present they must satisfy their constraints.

    Raises:
        ValueError: if any field violates its constraint.
    """
    incident_number = alarm.get("incident_number")
    if incident_number is not None:
        if not isinstance(incident_number, str):
            raise ValueError("incident_number must be a string")
        if not _INCIDENT_NUMBER_RE.match(incident_number):
            raise ValueError(
                "incident_number must be 1–50 characters matching ^[A-Za-z0-9\\-_]+$"
            )

    for field in _OPTIONAL_STRING_FIELDS:
        value = alarm.get(field)
        if value is not None:
            if not isinstance(value, str):
                raise ValueError(f"{field} must be a string")
            if len(value) > 500:
                raise ValueError(f"{field} must not exceed 500 characters")

    for field in _OPTIONAL_LIST_FIELDS:
        value = alarm.get(field)
        if value is not None:
            if not isinstance(value, list):
                raise ValueError(f"{field} must be a list")
            for i, item in enumerate(value):
                if not isinstance(item, str):
                    raise ValueError(f"{field}[{i}] must be a string")
                if len(item) > 200:
                    raise ValueError(f"{field}[{i}] must not exceed 200 characters")

    lat = alarm.get("latitude")
    if lat is not None:
        try:
            lat_f = float(lat)
        except (TypeError, ValueError):
            raise ValueError("latitude must be a number")
        if not (-90 <= lat_f <= 90):
            raise ValueError("latitude must be between -90 and 90")

    lon = alarm.get("longitude")
    if lon is not None:
        try:
            lon_f = float(lon)
        except (TypeError, ValueError):
            raise ValueError("longitude must be a number")
        if not (-180 <= lon_f <= 180):
            raise ValueError("longitude must be between -180 and 180")


def _serialize_history_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize a store history entry to a JSON-serializable dict."""
    from datetime import datetime

    alarm = entry.get("alarm") or {}
    received_at = entry.get("received_at")
    if isinstance(received_at, datetime):
        received_at_iso = received_at.isoformat()
    elif isinstance(received_at, str):
        received_at_iso = received_at
    else:
        received_at_iso = None

    timestamp = alarm.get("timestamp") or received_at_iso

    return {
        "timestamp": timestamp,
        "timestamp_display": alarm.get("timestamp_display"),
        "received_at": received_at_iso,
        "incident_number": alarm.get("incident_number"),
        "keyword": alarm.get("keyword") or alarm.get("subject"),
        "location": alarm.get("location"),
        "description": alarm.get("diagnosis"),
        "groups": alarm.get("groups"),
        "aao_groups": alarm.get("aao_groups"),
        "remark": alarm.get("remark"),
    }


def process_alarm(
    alarm: Dict[str, Any],
    store: Any,
    config: Any,
    get_settings: Callable[[], Dict[str, Any]],
    executor: Any = None,
) -> bool:
    """Process incoming alarm data: filter, geocode, fetch weather, and store.

    The alarm is stored immediately with coordinates=None, weather=None.
    Geocoding and weather lookup are performed in a background task and the
    store entry is updated once they complete.

    Args:
        alarm: Parsed alarm data from alarm-mail service.
        store: The AlarmStore instance.
        config: The AppConfig instance.
        get_settings: Callable returning current effective settings dict.
        executor: Optional ThreadPoolExecutor for background tasks.

    Returns:
        True if the alarm was accepted and stored, False if it was silently dropped.
    """
    LOGGER.info("Processing alarm: %s", alarm.get("incident_number"))

    validate_alarm_payload(alarm)

    incident_number = alarm.get("incident_number")
    if not incident_number:
        LOGGER.warning("Ignoring alarm without incident number (ENR)")
        return False

    if store.has_incident_number(incident_number):
        LOGGER.info(
            "Ignoring duplicate alarm with incident number: %s",
            incident_number,
        )
        return False

    effective_settings = get_settings()
    activation_filters = effective_settings.get("activation_groups", [])
    if activation_filters:
        dispatch_codes: Set[str] = set()
        for code in alarm.get("dispatch_group_codes") or []:
            if isinstance(code, str):
                dispatch_codes.add(code.upper())

        dispatch_texts: List[str] = []
        dispatch_groups = alarm.get("dispatch_groups")
        if isinstance(dispatch_groups, list):
            dispatch_texts = [str(item).upper() for item in dispatch_groups]
        elif isinstance(dispatch_groups, str):
            dispatch_texts = [dispatch_groups.upper()]

        match_found = False
        for target in activation_filters:
            target_upper = target.upper()
            if target_upper in dispatch_codes:
                match_found = True
                break
            if any(target_upper in text for text in dispatch_texts):
                match_found = True
                break

        if not match_found:
            LOGGER.info(
                "Ignoring alarm without configured groups: filters=%s",
                activation_filters,
            )
            return False

    # Store immediately with no coordinates/weather
    alarm_payload: Dict[str, Any] = {
        "alarm": alarm,
        "coordinates": None,
        "weather": None,
    }
    store.update(alarm_payload)

    # Run geocoding + weather in the background
    def _enrich() -> None:
        import requests as _requests
        from .geocode import geocode_location
        from .weather import fetch_weather

        session = _requests.Session()
        try:
            location = alarm.get("location")
            coordinates: Optional[Dict[str, float]] = None
            weather = None

            lat = alarm.get("latitude")
            lon = alarm.get("longitude")
            if lat is not None and lon is not None:
                try:
                    coordinates = {"lat": float(lat), "lon": float(lon)}
                except (TypeError, ValueError):
                    coordinates = None

            if coordinates is None and location:
                try:
                    coordinates = geocode_location(config.nominatim_base_url, location, session=session)
                except Exception as exc:
                    LOGGER.warning("Failed to geocode location %s: %s", location, exc)
                    try:
                        from .app import _increment_metric
                        _increment_metric("geocode_errors")
                    except ImportError:
                        pass

            if coordinates:
                try:
                    weather = fetch_weather(
                        config.weather_base_url,
                        config.weather_params,
                        float(coordinates["lat"]),
                        float(coordinates["lon"]),
                        session=session,
                    )
                except Exception as exc:
                    LOGGER.warning("Failed to fetch weather: %s", exc)
                    try:
                        from .app import _increment_metric
                        _increment_metric("weather_errors")
                    except ImportError:
                        pass

            # Update the stored alarm with enriched data
            store.update_enrichment(incident_number, coordinates, weather)
        finally:
            session.close()

    if executor is not None:
        executor.submit(_enrich)
    else:
        import threading
        threading.Thread(target=_enrich, daemon=True).start()

    return True


__all__ = ["process_alarm", "validate_alarm_payload", "_serialize_history_entry"]
