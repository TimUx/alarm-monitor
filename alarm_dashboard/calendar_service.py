"""Calendar service – fetches and parses iCal calendar events."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

LOGGER = logging.getLogger(__name__)

_MAX_CALENDAR_SIZE = 2 * 1024 * 1024  # 2 MB
_REQUEST_TIMEOUT = 10  # seconds
_DEFAULT_LOOK_AHEAD_DAYS = 30


def _is_safe_url(url: str) -> bool:
    """Return True only for http/https URLs with a non-empty host."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def _parse_ical_dt(value: str) -> Optional[datetime]:
    """Parse an iCal date or datetime value into a UTC-aware datetime.

    Handles:
    - All-day dates: ``YYYYMMDD``
    - UTC datetimes: ``YYYYMMDDTHHMMSSz``
    - Local datetimes (treated as UTC): ``YYYYMMDDTHHMMSS``
    """
    value = value.strip()

    if re.fullmatch(r"\d{8}", value):
        try:
            return datetime.strptime(value, "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    if re.fullmatch(r"\d{8}T\d{6}Z", value):
        try:
            return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return None

    m = re.fullmatch(r"(\d{8}T\d{6})", value)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y%m%dT%H%M%S").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return None

    return None


def _unfold_ical(text: str) -> str:
    """Unfold iCal folded lines (RFC 5545 §3.1)."""
    return re.sub(r"\r?\n[ \t]", "", text)


def _parse_events(ical_text: str) -> List[Dict[str, Any]]:
    """Extract VEVENT entries from raw iCal text."""
    events = []
    unfolded = _unfold_ical(ical_text)

    for vevent_match in re.finditer(
        r"BEGIN:VEVENT(.*?)END:VEVENT", unfolded, re.DOTALL
    ):
        block = vevent_match.group(1)
        event: Dict[str, Any] = {}

        for line in block.splitlines():
            if ":" not in line:
                continue
            colon_pos = line.index(":")
            prop_part = line[:colon_pos]
            value = line[colon_pos + 1:]
            name_base = prop_part.split(";")[0].upper()

            if name_base == "SUMMARY":
                event["summary"] = value
            elif name_base == "DTSTART":
                dt = _parse_ical_dt(value)
                if dt:
                    event["start"] = dt
            elif name_base == "DTEND":
                dt = _parse_ical_dt(value)
                if dt:
                    event["end"] = dt
            elif name_base == "DESCRIPTION":
                event["description"] = value
            elif name_base == "LOCATION":
                event["location_name"] = value

        if "summary" in event and "start" in event:
            events.append(event)

    return events


def fetch_calendar_events(
    urls: List[str],
    max_events: int = 10,
    look_ahead_days: int = _DEFAULT_LOOK_AHEAD_DAYS,
) -> List[Dict[str, Any]]:
    """Fetch and merge upcoming events from a list of iCal URLs.

    Args:
        urls: List of iCal (.ics) URLs to fetch.
        max_events: Maximum number of events to return.
        look_ahead_days: How many days ahead to include events for.

    Returns:
        List of serialised event dicts sorted by start time.
    """
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=look_ahead_days)
    all_events: List[Dict[str, Any]] = []

    for url in urls:
        url = url.strip()
        if not url:
            continue
        if not _is_safe_url(url):
            LOGGER.warning("Skipping unsafe calendar URL: %.80s", url)
            continue

        try:
            response = requests.get(
                url,
                timeout=_REQUEST_TIMEOUT,
                headers={"User-Agent": "AlarmDashboard-Calendar/1.0"},
                stream=True,
            )
            response.raise_for_status()

            content = b""
            for chunk in response.iter_content(chunk_size=8192):
                content += chunk
                if len(content) > _MAX_CALENDAR_SIZE:
                    LOGGER.warning(
                        "Calendar response too large, truncating: %.80s", url
                    )
                    break

            ical_text = content.decode("utf-8", errors="replace")
            events = _parse_events(ical_text)

            for event in events:
                start = event.get("start")
                if not isinstance(start, datetime):
                    continue
                if now <= start <= cutoff:
                    all_events.append(event)

        except requests.RequestException as exc:
            LOGGER.warning("Failed to fetch calendar %.80s: %s", url, exc)
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.warning("Error processing calendar %.80s: %s", url, exc)

    all_events.sort(key=lambda e: e["start"])

    result = []
    for event in all_events[:max_events]:
        serialized: Dict[str, Any] = {
            "summary": event.get("summary", ""),
            "start": event["start"].isoformat(),
            "end": event["end"].isoformat() if event.get("end") else None,
        }
        if event.get("description"):
            serialized["description"] = event["description"]
        if event.get("location_name"):
            serialized["location_name"] = event["location_name"]
        result.append(serialized)

    return result


__all__ = ["fetch_calendar_events"]
