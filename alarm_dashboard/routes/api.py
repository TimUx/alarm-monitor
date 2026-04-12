"""API Blueprint – all /api/* route handlers."""

from __future__ import annotations

import hmac
import json
import logging
import re
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests as http_requests
from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context

from ..alarm_processor import _serialize_history_entry, process_alarm
from ..app import _limiter

LOGGER = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__)

_INCIDENT_NUMBER_RE = re.compile(r'^[A-Za-z0-9\-_]{1,50}$')
_MESSAGE_ID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
)


# ---------------------------------------------------------------------------
# Helpers – access shared state from app config
# ---------------------------------------------------------------------------

def _get_store():
    return current_app.config["ALARM_STORE"]


def _get_config():
    return current_app.config["APP_CONFIG"]


def _get_settings_store():
    return current_app.config["SETTINGS_STORE"]


def _get_messenger():
    return current_app.config.get("ALARM_MESSENGER")


def _get_subscribers():
    return current_app.config["SSE_SUBSCRIBERS"]


def _get_subscribers_lock():
    return current_app.config["SSE_SUBSCRIBERS_LOCK"]


def _get_weather_cache():
    return current_app.config["WEATHER_CACHE"]


def _get_message_store():
    return current_app.config.get("MESSAGE_STORE")


def _get_effective_settings() -> Dict[str, Any]:
    from ..app import get_effective_settings
    return get_effective_settings(_get_settings_store(), _get_config())


def _build_idle_response(last_alarm: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    from ..app import _executor
    config = _get_config()
    effective_settings = _get_effective_settings()
    weather = None
    lat = effective_settings["default_latitude"]
    lon = effective_settings["default_longitude"]
    if lat is not None and lon is not None:
        weather = _get_weather_cache().get_weather(
            config.weather_base_url,
            config.weather_params,
            lat,
            lon,
            executor=_executor,
        )
    last_alarm_entry: Optional[Dict[str, Any]] = None
    if last_alarm:
        last_alarm_entry = _serialize_history_entry(last_alarm)

    return {
        "mode": "idle",
        "alarm": None,
        "weather": weather,
        "location": effective_settings["default_location_name"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "last_alarm": last_alarm_entry,
    }


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

@api_bp.route("/api/alarm", methods=["POST"])
@_limiter.limit("60 per minute")
def receive_alarm():
    """Receive alarm data via API from alarm-mail service."""
    from ..app import _executor, _increment_metric
    config = _get_config()
    store = _get_store()
    subscribers = _get_subscribers()
    subscribers_lock = _get_subscribers_lock()

    api_key = request.headers.get("X-API-Key") or ""
    if not config.api_key or not hmac.compare_digest(api_key, config.api_key):
        LOGGER.warning("Unauthorized API access attempt")
        return jsonify({"error": "Unauthorized"}), 401

    alarm_data = request.get_json()
    if not alarm_data:
        LOGGER.warning("Received empty alarm data")
        return jsonify({"error": "Invalid request"}), 400

    _increment_metric("alarms_received")

    try:
        stored = process_alarm(alarm_data, store, config, _get_effective_settings, _executor)
        if stored:
            _increment_metric("alarms_stored")
            with subscribers_lock:
                for evt in subscribers:
                    evt.set()
        response = jsonify({"status": "ok"})
        response.headers["Cache-Control"] = "no-store"
        return response, 200
    except ValueError as exc:
        LOGGER.warning("Invalid alarm payload: %s", exc)
        # Validation errors from validate_alarm_payload() are intentionally surfaced
        # to callers so they can correct the payload.
        error_message = str(exc)
        return jsonify({"error": error_message}), 400
    except Exception:
        LOGGER.error("Error processing alarm", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@api_bp.route("/api/alarm")
def api_alarm():
    config = _get_config()
    store = _get_store()

    alarm_payload = store.latest()
    if alarm_payload is None:
        resp = jsonify(_build_idle_response(None))
        resp.headers["Cache-Control"] = "no-store"
        return resp

    received_at = alarm_payload.get("received_at")
    if isinstance(received_at, str):
        try:
            received_at = datetime.fromisoformat(received_at)
        except ValueError:
            received_at = None

    if not isinstance(received_at, datetime):
        received_at = None

    display_duration = max(1, config.display_duration_minutes)
    if received_at and received_at + timedelta(minutes=display_duration) < datetime.now(timezone.utc):
        resp = jsonify(_build_idle_response(alarm_payload))
        resp.headers["Cache-Control"] = "no-store"
        return resp

    payload: Dict[str, Any] = {
        "mode": "alarm",
        "alarm": alarm_payload.get("alarm"),
        "coordinates": alarm_payload.get("coordinates"),
        "weather": alarm_payload.get("weather"),
        "received_at": (
            received_at.isoformat() if isinstance(received_at, datetime) else None
        ),
    }
    resp = jsonify(payload)
    resp.headers["Cache-Control"] = "no-store"
    return resp


@api_bp.route("/api/stream")
def api_stream():
    """Server-Sent Events endpoint for real-time alarm updates."""
    from flask import jsonify as _jsonify
    store = _get_store()
    subscribers = _get_subscribers()
    subscribers_lock = _get_subscribers_lock()

    # Check connection limit before setting up the stream
    with subscribers_lock:
        if len(subscribers) >= 20:
            return _jsonify({"error": "Too many concurrent streams"}), 503

    def generate():
        evt = threading.Event()
        with subscribers_lock:
            subscribers.append(evt)
        try:
            yield "data: " + json.dumps({"type": "connected"}) + "\n\n"
            while True:
                try:
                    triggered = evt.wait(timeout=30)
                    evt.clear()
                    if triggered:
                        alarm_payload = store.latest()
                        if alarm_payload is not None:
                            received_at = alarm_payload.get("received_at")
                            if isinstance(received_at, datetime):
                                received_at = received_at.isoformat()
                            event_data = json.dumps({
                                "type": "alarm",
                                "alarm": alarm_payload.get("alarm"),
                                "coordinates": alarm_payload.get("coordinates"),
                                "weather": alarm_payload.get("weather"),
                                "received_at": received_at,
                            })
                        else:
                            event_data = json.dumps({"type": "idle"})
                        yield "data: " + event_data + "\n\n"
                    else:
                        yield "data: " + json.dumps({"type": "heartbeat"}) + "\n\n"
                except (BrokenPipeError, ConnectionResetError, GeneratorExit):
                    LOGGER.debug("SSE client disconnected")
                    break
        finally:
            with subscribers_lock:
                try:
                    subscribers.remove(evt)
                except ValueError:
                    pass

    resp = Response(stream_with_context(generate()), mimetype="text/event-stream")
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


@api_bp.route("/api/alarm/participants/<incident_number>")
def api_participants(incident_number: str):
    """Get participants for an alarm by incident number."""
    messenger = _get_messenger()

    if not _INCIDENT_NUMBER_RE.match(incident_number):
        return jsonify({"error": "Invalid incident number"}), 400

    if not messenger:
        return jsonify({"error": "Messenger not configured"}), 503

    participants = messenger.get_participants(incident_number)
    if participants is None:
        return jsonify({"error": "Failed to fetch participants"}), 500

    return jsonify({"participants": participants})


@api_bp.route("/api/history")
def api_history():
    store = _get_store()

    limit: Optional[int] = None
    raw_limit = request.args.get("limit")
    if raw_limit:
        try:
            limit = max(1, min(500, int(raw_limit)))
        except ValueError:
            limit = None

    offset = 0
    raw_offset = request.args.get("offset")
    if raw_offset:
        try:
            offset = max(0, min(10000, int(raw_offset)))
        except ValueError:
            offset = 0

    history_entries = store.history(limit=limit, offset=offset)
    history_payload: List[Dict[str, Any]] = [
        _serialize_history_entry(entry) for entry in history_entries
    ]
    return jsonify({"history": history_payload})


@api_bp.route("/api/route")
def api_route():
    """Proxy routing requests to OpenRouteService."""
    config = _get_config()

    if not config.ors_api_key:
        return jsonify({"error": "Routing not configured"}), 503

    try:
        start_lat = float(request.args["start_lat"])
        start_lon = float(request.args["start_lon"])
        end_lat = float(request.args["end_lat"])
        end_lon = float(request.args["end_lon"])
    except (KeyError, ValueError, TypeError):
        return jsonify({"error": "start_lat, start_lon, end_lat, end_lon are required numeric parameters"}), 400

    body = {
        "coordinates": [[start_lon, start_lat], [end_lon, end_lat]],
        "instructions": True,
        "language": "de",
    }
    try:
        ors_response = http_requests.post(
            "https://api.openrouteservice.org/v2/directions/driving-car?geometry_format=geojson",
            json=body,
            headers={
                "Authorization": config.ors_api_key,
                "Content-Type": "application/json",
            },
            timeout=15,
        )
    except Exception as exc:
        LOGGER.warning("ORS request failed: %s", exc)
        return jsonify({"error": "Routing service unavailable"}), 502

    if ors_response.status_code != 200:
        LOGGER.warning("ORS returned non-200 status: %s", ors_response.status_code)
        return jsonify({"error": "Routing service error"}), 502

    try:
        data = ors_response.json()
    except Exception as exc:
        LOGGER.warning("Failed to parse ORS response: %s", exc)
        data = {}

    resp = jsonify(data)
    resp.headers["Cache-Control"] = "no-store"
    return resp


@api_bp.route("/api/settings", methods=["GET"])
def api_get_settings():
    """Get current settings."""
    effective_settings = _get_effective_settings()
    groups_str = ",".join(effective_settings.get("activation_groups", []))
    calendar_urls = effective_settings.get("calendar_urls", [])
    calendar_urls_str = "\n".join(calendar_urls) if calendar_urls else ""
    resp = jsonify({
        "fire_department_name": effective_settings["fire_department_name"],
        "default_latitude": effective_settings["default_latitude"],
        "default_longitude": effective_settings["default_longitude"],
        "default_location_name": effective_settings["default_location_name"],
        "activation_groups": groups_str,
        "calendar_urls": calendar_urls_str,
        "ntfy_topic_url": effective_settings.get("ntfy_topic_url") or "",
        "ntfy_poll_interval": effective_settings.get("ntfy_poll_interval", 60),
        "message_default_ttl_minutes": effective_settings.get("message_default_ttl_minutes", 60),
    })
    resp.headers["Cache-Control"] = "no-store"
    return resp


@api_bp.route("/api/settings", methods=["POST"])
def api_update_settings():
    """Update settings."""
    from ..app import generate_csrf_token, generate_csrf_token_for_hour_offset
    config = _get_config()
    settings_store = _get_settings_store()

    provided = request.headers.get("X-Settings-Password") or ""
    if not config.settings_password or not hmac.compare_digest(provided, config.settings_password):
        LOGGER.warning("Unauthorized settings update attempt")
        return jsonify({"error": "Unauthorized"}), 401

    csrf_header = request.headers.get("X-CSRF-Token") or ""
    current_token = generate_csrf_token(config.settings_password)
    prev_token = generate_csrf_token_for_hour_offset(config.settings_password, -1)
    if not (hmac.compare_digest(csrf_header, current_token) or
            hmac.compare_digest(csrf_header, prev_token)):
        LOGGER.warning("Invalid CSRF token on settings update")
        return jsonify({"error": "Invalid CSRF token"}), 403

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    updates = {}

    if "fire_department_name" in data:
        updates["fire_department_name"] = str(data["fire_department_name"]).strip()

    has_lat = "default_latitude" in data and data["default_latitude"]
    has_lon = "default_longitude" in data and data["default_longitude"]

    if has_lat and has_lon:
        try:
            lat = float(data["default_latitude"])
            lon = float(data["default_longitude"])
            if not (-90 <= lat <= 90):
                return jsonify({"error": "Latitude must be between -90 and 90"}), 400
            if not (-180 <= lon <= 180):
                return jsonify({"error": "Longitude must be between -180 and 180"}), 400
            updates["default_latitude"] = lat
            updates["default_longitude"] = lon
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid latitude or longitude format"}), 400
    elif has_lat or has_lon:
        return jsonify({"error": "Both latitude and longitude must be provided together"}), 400
    elif ("default_latitude" in data and not data["default_latitude"] and
          "default_longitude" in data and not data["default_longitude"]):
        updates["default_latitude"] = None
        updates["default_longitude"] = None

    if "default_location_name" in data:
        updates["default_location_name"] = (
            str(data["default_location_name"]).strip() if data["default_location_name"] else None
        )

    if "activation_groups" in data:
        groups_str = str(data["activation_groups"]).strip()
        if groups_str:
            groups = [g.strip().upper() for g in groups_str.split(",") if g.strip()]
        else:
            groups = []
        updates["activation_groups"] = groups

    if "calendar_urls" in data:
        import re as _re
        raw_urls = str(data["calendar_urls"]).strip() if data["calendar_urls"] else ""
        if raw_urls:
            calendar_urls = [u.strip() for u in _re.split(r"[\n,]+", raw_urls) if u.strip()]
        else:
            calendar_urls = []
        updates["calendar_urls"] = calendar_urls

    if "ntfy_topic_url" in data:
        ntfy_url = str(data["ntfy_topic_url"]).strip() if data["ntfy_topic_url"] else ""
        updates["ntfy_topic_url"] = ntfy_url if ntfy_url else None

    if "ntfy_poll_interval" in data and data["ntfy_poll_interval"] not in (None, ""):
        try:
            interval = int(data["ntfy_poll_interval"])
            if interval < 10:
                return jsonify({"error": "ntfy_poll_interval must be at least 10 seconds"}), 400
            updates["ntfy_poll_interval"] = interval
        except (TypeError, ValueError):
            return jsonify({"error": "ntfy_poll_interval must be an integer"}), 400

    if "message_default_ttl_minutes" in data and data["message_default_ttl_minutes"] not in (None, ""):
        try:
            ttl = int(data["message_default_ttl_minutes"])
            if ttl < 1:
                return jsonify({"error": "message_default_ttl_minutes must be at least 1"}), 400
            updates["message_default_ttl_minutes"] = ttl
        except (TypeError, ValueError):
            return jsonify({"error": "message_default_ttl_minutes must be an integer"}), 400

    settings_store.update(updates)
    LOGGER.info("Settings updated: %s", updates)

    resp = jsonify({"status": "ok", "settings": updates})
    resp.headers["Cache-Control"] = "no-store"
    return resp


@api_bp.route("/api/calendar")
def api_calendar():
    """Return upcoming calendar events from configured iCal URLs."""
    from ..calendar_service import fetch_calendar_events
    effective_settings = _get_effective_settings()
    calendar_urls = effective_settings.get("calendar_urls", [])

    if not calendar_urls:
        resp = jsonify({"events": []})
        resp.headers["Cache-Control"] = "no-store"
        return resp

    try:
        events = fetch_calendar_events(calendar_urls)
    except Exception:
        LOGGER.error("Failed to fetch calendar events", exc_info=True)
        events = []

    resp = jsonify({"events": events})
    resp.headers["Cache-Control"] = "no-store"
    return resp


@api_bp.route("/api/messages", methods=["GET"])
def api_get_messages():
    """Return all active (non-expired) dashboard messages."""
    store = _get_message_store()
    messages = store.get_active() if store is not None else []
    resp = jsonify({"messages": messages})
    resp.headers["Cache-Control"] = "no-store"
    return resp


@api_bp.route("/api/messages", methods=["POST"])
@_limiter.limit("30 per minute")
def api_post_message():
    """Create a new dashboard message (requires X-API-Key)."""
    config = _get_config()

    api_key = request.headers.get("X-API-Key") or ""
    if not config.api_key or not hmac.compare_digest(api_key, config.api_key):
        LOGGER.warning("Unauthorized message creation attempt")
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    text = str(data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400
    if len(text) > 500:
        return jsonify({"error": "text must not exceed 500 characters"}), 400

    raw_ttl = data.get("ttl_minutes", 60)
    try:
        ttl_minutes = int(raw_ttl)
    except (TypeError, ValueError):
        return jsonify({"error": "ttl_minutes must be an integer"}), 400

    store = _get_message_store()
    if store is None:
        return jsonify({"error": "Message store not available"}), 503

    subscribers = _get_subscribers()
    subscribers_lock = _get_subscribers_lock()

    def _trigger_sse() -> None:
        with subscribers_lock:
            for evt in subscribers:
                evt.set()

    message = store.add(text, ttl_minutes, on_stored=_trigger_sse)

    resp = jsonify({"status": "ok", "message": message})
    resp.headers["Cache-Control"] = "no-store"
    return resp, 201


@api_bp.route("/api/messages/<message_id>", methods=["DELETE"])
def api_delete_message(message_id: str):
    """Delete a dashboard message by ID (requires X-API-Key)."""
    config = _get_config()

    api_key = request.headers.get("X-API-Key") or ""
    if not config.api_key or not hmac.compare_digest(api_key, config.api_key):
        LOGGER.warning("Unauthorized message deletion attempt")
        return jsonify({"error": "Unauthorized"}), 401

    if not _MESSAGE_ID_RE.match(message_id):
        return jsonify({"error": "Invalid message ID"}), 400

    store = _get_message_store()
    if store is None:
        return jsonify({"error": "Message store not available"}), 503

    deleted = store.delete(message_id)
    if not deleted:
        return jsonify({"error": "Message not found"}), 404

    resp = jsonify({"status": "ok"})
    resp.headers["Cache-Control"] = "no-store"
    return resp


@api_bp.route("/api/metrics")
def api_metrics():
    """Prometheus-compatible plain text metrics endpoint.

    Requires X-Metrics-Token: <ALARM_DASHBOARD_METRICS_TOKEN> header.
    Returns 404 if ALARM_DASHBOARD_METRICS_TOKEN is not configured.
    """
    import os
    from ..app import _metrics, _metrics_lock

    metrics_token = os.environ.get("ALARM_DASHBOARD_METRICS_TOKEN", "")
    if not metrics_token:
        return jsonify({"error": "Not found"}), 404

    token = request.headers.get("X-Metrics-Token", "")
    if not hmac.compare_digest(token, metrics_token):
        return jsonify({"error": "Unauthorized"}), 401

    store = _get_store()
    subscribers = _get_subscribers()

    with _metrics_lock:
        m = dict(_metrics)

    lines = []
    metric_defs = [
        ("alarms_received", "Total alarms received via POST /api/alarm", "counter"),
        ("alarms_stored", "Total alarms successfully stored", "counter"),
        ("geocode_errors", "Total geocoding errors", "counter"),
        ("weather_errors", "Total weather fetch errors", "counter"),
    ]
    for key, help_text, mtype in metric_defs:
        lines.append(f"# HELP alarm_dashboard_{key}_total {help_text}")
        lines.append(f"# TYPE alarm_dashboard_{key}_total {mtype}")
        lines.append(f"alarm_dashboard_{key}_total {m.get(key, 0)}")

    lines.append("# HELP alarm_dashboard_sse_active_connections Current SSE connections")
    lines.append("# TYPE alarm_dashboard_sse_active_connections gauge")
    lines.append(f"alarm_dashboard_sse_active_connections {len(subscribers)}")

    lines.append("# HELP alarm_dashboard_history_size Total alarm history entries")
    lines.append("# TYPE alarm_dashboard_history_size gauge")
    lines.append(f"alarm_dashboard_history_size {store.history_count()}")

    text = "\n".join(lines) + "\n"
    return text, 200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"}
