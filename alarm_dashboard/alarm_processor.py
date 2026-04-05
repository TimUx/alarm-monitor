"""Alarm processing logic: geocoding, weather lookup, and store updates."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

LOGGER = logging.getLogger(__name__)


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
        dispatch_codes: set = set()
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
        from .geocode import geocode_location
        from .weather import fetch_weather

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
                coordinates = geocode_location(config.nominatim_base_url, location)
            except Exception as exc:
                LOGGER.warning("Failed to geocode location %s: %s", location, exc)

        if coordinates:
            try:
                weather = fetch_weather(
                    config.weather_base_url,
                    config.weather_params,
                    float(coordinates["lat"]),
                    float(coordinates["lon"]),
                )
            except Exception as exc:
                LOGGER.warning("Failed to fetch weather: %s", exc)

        # Update the stored alarm with enriched data
        store.update_enrichment(incident_number, coordinates, weather)

    if executor is not None:
        executor.submit(_enrich)
    else:
        import threading
        threading.Thread(target=_enrich, daemon=True).start()

    return True


__all__ = ["process_alarm", "_serialize_history_entry"]
