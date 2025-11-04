"""Utilities for parsing alarm e-mails into structured payloads."""

from __future__ import annotations

import email
import email.policy
from datetime import datetime
import re
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET


def _parse_body(message: email.message.Message) -> str:
    """Extract a text body from the email message."""

    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                charset = part.get_content_charset() or "utf-8"
                return part.get_payload(decode=True).decode(charset, errors="replace")
    else:
        charset = message.get_content_charset() or "utf-8"
        return message.get_payload(decode=True).decode(charset, errors="replace")
    return ""


def _parse_timestamp(value: Optional[str]) -> Dict[str, Optional[str]]:
    """Return ISO and display representations for the provided timestamp string."""

    if not value:
        return {"timestamp": None, "timestamp_display": None}

    value = value.strip()
    for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M"):
        try:
            parsed = datetime.strptime(value, fmt)
            return {"timestamp": parsed.isoformat(), "timestamp_display": value}
        except ValueError:
            continue

    # Fallback to returning the original value if parsing fails.
    return {"timestamp": value, "timestamp_display": value}


def _extract_text(element: Optional[ET.Element]) -> Optional[str]:
    if element is None:
        return None
    if element.text is None:
        return None
    text = element.text.strip()
    return text or None


def _parse_incident_xml(body: str) -> Optional[Dict[str, Any]]:
    """Parse the Leitstelle XML payload into an alarm dictionary."""

    stripped = body.strip()
    start = stripped.find("<INCIDENT")
    if start == -1:
        return None

    end = stripped.find("</INCIDENT>", start)
    if end != -1:
        end += len("</INCIDENT>")
        xml_payload = stripped[start:end]
    else:
        xml_payload = stripped[start:]

    try:
        root = ET.fromstring(xml_payload)
    except ET.ParseError:
        return None

    if root.tag.upper() != "INCIDENT":
        return None

    def get_text(name: str) -> Optional[str]:
        return _extract_text(root.find(name))

    keyword_primary = get_text("ESTICHWORT_1") or get_text("STICHWORT")
    keyword_secondary = get_text("ESTICHWORT_2")
    diagnosis = get_text("DIAGNOSE")
    remark = get_text("EO_BEMERKUNG") or get_text("EOZUSATZ")

    timestamp_values = _parse_timestamp(get_text("EBEGINN"))

    street = get_text("STRASSE")
    house_number = get_text("HAUSNUMMER")
    street_line = " ".join(part for part in [street, house_number] if part)
    village = get_text("ORTSTEIL")
    town = get_text("ORT")
    object_name = get_text("OBJEKT")
    additional = get_text("ORTSZUSATZ")

    location_parts = [street_line or object_name, additional, village, town]
    location = ", ".join(part for part in location_parts if part)
    if not location:
        location = town or village or street_line or object_name

    groups_text = get_text("AAO")
    aao_groups: List[str] = []
    if groups_text:
        aao_groups = [part.strip() for part in groups_text.split(";") if part.strip()]

    dispatch_groups: List[str] = []
    dispatch_codes: List[str] = []

    einsatz = root.find("EINSATZMASSNAHMEN")
    if einsatz is not None:
        tme = einsatz.find("TME")
        if tme is not None:
            for child in tme.findall("BEZEICHNUNG"):
                text = _extract_text(child)
                if text:
                    dispatch_groups.append(text)
                    for code in re.findall(r"\b([A-ZÄÖÜ]{1,}[0-9]{1,})\b", text):
                        dispatch_codes.append(code.upper())

    if dispatch_codes:
        dispatch_codes = list(dict.fromkeys(dispatch_codes))

    combined_groups: List[str] = []
    combined_groups.extend(aao_groups)
    combined_groups.extend(dispatch_groups)
    groups: Optional[List[str]]
    groups = combined_groups if combined_groups else None

    lat = get_text("KOORDINATE_LAT")
    lon = get_text("KOORDINATE_LON")
    try:
        latitude = float(lat) if lat else None
    except ValueError:
        latitude = None
    try:
        longitude = float(lon) if lon else None
    except ValueError:
        longitude = None

    keyword_display_parts = [keyword_primary]
    if diagnosis and diagnosis not in keyword_display_parts:
        keyword_display_parts.append(diagnosis)
    keyword_display = " – ".join(part for part in keyword_display_parts if part)

    alarm: Dict[str, Optional[str]] = {
        **timestamp_values,
        "keyword": keyword_display or keyword_primary,
        "keyword_primary": keyword_primary,
        "keyword_secondary": keyword_secondary,
        "diagnosis": diagnosis,
        "remark": remark,
        "description": diagnosis,
        "groups": groups,
        "dispatch_groups": dispatch_groups or None,
        "dispatch_group_codes": dispatch_codes or None,
        "location": location,
        "location_details": {
            "street": street_line or None,
            "village": village,
            "town": town,
            "object": object_name,
            "additional": additional,
        },
        "latitude": latitude,
        "longitude": longitude,
    }

    return alarm


def parse_alarm(raw_email: bytes) -> Dict[str, Any]:
    """Parse the raw email into a dictionary of alarm fields."""

    message = email.message_from_bytes(raw_email, policy=email.policy.default)
    body = _parse_body(message)

    xml_alarm = _parse_incident_xml(body)
    if xml_alarm is not None:
        xml_alarm["subject"] = message.get("Subject")
        return xml_alarm

    fields = {
        "timestamp": None,
        "timestamp_display": None,
        "keyword": None,
        "description": None,
        "groups": None,
        "location": None,
    }

    for line in body.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key in ("uhrzeit", "zeit", "timestamp"):
            fields.update(_parse_timestamp(value))
        elif key in ("einsatzstichwort", "stichwort", "keyword"):
            fields["keyword"] = value
        elif key in ("beschreibung", "description"):
            fields["description"] = value
        elif key in ("alarmierte gruppen", "gruppen", "groups"):
            fields["groups"] = value
        elif key in ("ort", "location"):
            fields["location"] = value

    if fields["timestamp"] is None:
        date_header = message.get("Date")
        if date_header:
            try:
                parsed = email.utils.parsedate_to_datetime(date_header)
                fields["timestamp"] = parsed.isoformat()
                fields["timestamp_display"] = parsed.isoformat()
            except (TypeError, ValueError):
                fields["timestamp"] = date_header
                fields["timestamp_display"] = date_header
        else:
            now_iso = datetime.utcnow().isoformat()
            fields["timestamp"] = now_iso
            fields["timestamp_display"] = now_iso

    if fields["description"] is None:
        stripped = body.strip()
        fields["description"] = stripped or None

    fields["subject"] = message.get("Subject")

    return fields


__all__ = ["parse_alarm"]
