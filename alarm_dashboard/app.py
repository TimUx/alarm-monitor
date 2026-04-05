"""Main Flask application exposing the alarm dashboard."""

from __future__ import annotations

import atexit
import concurrent.futures
import hmac
import json
import logging
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests as http_requests
from flask import Flask, Response, jsonify, render_template, request, stream_with_context, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from .alarm_processor import _serialize_history_entry, process_alarm
from .config import AppConfig, load_config
from .messenger import create_messenger
from .storage import AlarmStore, SettingsStore
from .weather_cache import get_cached_weather

LOGGER = logging.getLogger(__name__)

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
atexit.register(_executor.shutdown, wait=False)

_INCIDENT_NUMBER_RE = re.compile(r'^[A-Za-z0-9\-_]{1,50}$')


# ---------------------------------------------------------------------------
# Module-level helper for effective settings
# ---------------------------------------------------------------------------


def get_effective_settings(settings_store: SettingsStore, config: AppConfig) -> Dict[str, Any]:
    """Get effective settings merging stored values with config defaults."""
    stored = settings_store.get_all()
    return {
        "fire_department_name": stored.get("fire_department_name", config.fire_department_name),
        "default_latitude": stored.get("default_latitude", config.default_latitude),
        "default_longitude": stored.get("default_longitude", config.default_longitude),
        "default_location_name": stored.get("default_location_name", config.default_location_name),
        "activation_groups": stored.get("activation_groups", config.activation_groups),
    }


def create_app(config: Optional[AppConfig] = None) -> Flask:
    """Application factory used by Flask."""

    if os.environ.get("ALARM_DASHBOARD_JSON_LOGGING", "").lower() == "true":
        from pythonjsonlogger import jsonlogger  # type: ignore[import]
        handler = logging.StreamHandler()
        fmt = jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        )
        handler.setFormatter(fmt)
        logging.root.handlers = []
        logging.root.addHandler(handler)
        logging.root.setLevel(logging.INFO)
    else:
        logging.basicConfig(level=logging.INFO)

    if config is None:
        config = load_config()

    app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"))
    app.config["APP_VERSION"] = config.app_version
    app.config["APP_VERSION_URL"] = config.app_version_url
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 3600

    if config.history_file:
        persistence_path = Path(config.history_file)
    else:
        persistence_path = Path(app.instance_path) / "alarm_history.json"
        config.history_file = str(persistence_path)

    store = AlarmStore(persistence_path=persistence_path)
    app.config["ALARM_STORE"] = store
    app.config["APP_CONFIG"] = config

    # Initialize settings store
    if config.settings_file:
        settings_path = Path(config.settings_file)
    else:
        settings_path = Path(app.instance_path) / "settings.json"
    settings_store = SettingsStore(persistence_path=settings_path)
    app.config["SETTINGS_STORE"] = settings_store

    # SSE subscriber registry – one threading.Event per connected client
    _subscribers: List[threading.Event] = []
    _subscribers_lock = threading.Lock()
    app.config["SSE_SUBSCRIBERS"] = _subscribers

    def get_settings() -> Dict[str, Any]:
        return get_effective_settings(settings_store, config)

    # Rate limiter – keyed by client IP
    limiter = Limiter(key_func=get_remote_address, app=app, default_limits=[])

    @app.after_request
    def set_api_cache_headers(response):
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache"
        return response

    # Initialize alarm messenger if configured
    messenger = create_messenger(
        config.messenger_server_url, config.messenger_api_key
    )
    app.config["ALARM_MESSENGER"] = messenger

    # API endpoint for receiving alarms from alarm-mail service
    @app.route("/api/alarm", methods=["POST"])
    @limiter.limit("60 per minute")
    def receive_alarm():
        """Receive alarm data via API from alarm-mail service."""
        # Verify API key using constant-time comparison to prevent timing attacks
        api_key = request.headers.get("X-API-Key") or ""
        if not config.api_key or not hmac.compare_digest(api_key, config.api_key):
            LOGGER.warning("Unauthorized API access attempt")
            return jsonify({"error": "Unauthorized"}), 401

        # Get alarm data from request
        alarm_data = request.get_json()
        if not alarm_data:
            LOGGER.warning("Received empty alarm data")
            return jsonify({"error": "Invalid request"}), 400

        try:
            stored = process_alarm(alarm_data, store, config, get_settings, _executor)
            if stored:
                # Notify all connected SSE clients
                with _subscribers_lock:
                    for evt in _subscribers:
                        evt.set()
            response = jsonify({"status": "ok"})
            response.headers["Cache-Control"] = "no-store"
            return response, 200
        except Exception as exc:
            LOGGER.error("Error processing alarm: %s", exc)
            return jsonify({"error": "Internal server error"}), 500

    @app.route("/")
    def dashboard() -> str:
        crest_url = url_for("static", filename="img/crest.png")
        effective_settings = get_settings()
        return render_template(
            "dashboard.html",
            crest_url=crest_url,
            department_name=effective_settings["fire_department_name"],
            display_duration_minutes=config.display_duration_minutes,
            app_version=config.app_version,
            app_version_url=config.app_version_url,
        )

    @app.route("/navigation")
    def navigation_page() -> str:
        crest_url = url_for("static", filename="img/crest.png")
        effective_settings = get_settings()
        return render_template(
            "navigation.html",
            crest_url=crest_url,
            department_name=effective_settings["fire_department_name"],
            default_latitude=effective_settings["default_latitude"],
            default_longitude=effective_settings["default_longitude"],
            default_location_name=effective_settings["default_location_name"],
            app_version=config.app_version,
            app_version_url=config.app_version_url,
        )

    @app.route("/history")
    def history_page() -> str:
        raw_entries = store.history()
        serialized = [_serialize_history_entry(entry) for entry in raw_entries]
        decorated = []
        for entry in serialized:
            timestamp = entry.get("timestamp") or entry.get("received_at")
            parsed: Optional[datetime]
            parsed = None
            if timestamp:
                try:
                    parsed = datetime.fromisoformat(timestamp)
                except ValueError:
                    parsed = None
            display_date = parsed.strftime("%d.%m.%Y") if parsed else "–"
            display_time = parsed.strftime("%H:%M") if parsed else "–"
            decorated.append({
                **entry,
                "display_date": display_date,
                "display_time": display_time,
            })
        crest_url = url_for("static", filename="img/crest.png")
        effective_settings = get_settings()
        return render_template(
            "history.html",
            entries=decorated,
            crest_url=crest_url,
            department_name=effective_settings["fire_department_name"],
            app_version=config.app_version,
            app_version_url=config.app_version_url,
        )

    @app.route("/mobile")
    def mobile_dashboard() -> str:
        crest_url = url_for("static", filename="img/crest.png")
        effective_settings = get_settings()
        return render_template(
            "mobile.html",
            crest_url=crest_url,
            department_name=effective_settings["fire_department_name"],
            app_version=config.app_version,
            app_version_url=config.app_version_url,
        )

    def _build_idle_response(last_alarm: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        effective_settings = get_settings()
        weather = None
        lat = effective_settings["default_latitude"]
        lon = effective_settings["default_longitude"]
        if lat is not None and lon is not None:
            weather = get_cached_weather(
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

    @app.route("/api/alarm")
    def api_alarm():
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

    @app.route("/api/stream")
    def api_stream():
        """Server-Sent Events endpoint for real-time alarm updates.

        Clients connect and receive:
        - An immediate ``{"type": "connected"}`` event confirming the connection.
        - A ``{"type": "alarm", ...}`` event whenever a new alarm is received.
        - A heartbeat comment line every 30 seconds to keep the connection alive.
        """

        def generate():
            evt = threading.Event()
            with _subscribers_lock:
                _subscribers.append(evt)
            try:
                # Immediately confirm the connection
                yield "data: " + json.dumps({"type": "connected"}) + "\n\n"
                while True:
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
                        # Heartbeat comment keeps proxies and load balancers from
                        # closing the idle connection.
                        yield ": heartbeat\n\n"
            finally:
                with _subscribers_lock:
                    try:
                        _subscribers.remove(evt)
                    except ValueError:
                        pass

        resp = Response(stream_with_context(generate()), mimetype="text/event-stream")
        resp.headers["X-Accel-Buffering"] = "no"
        return resp

    @app.route("/api/alarm/participants/<incident_number>")
    @limiter.limit("30 per minute")
    def api_participants(incident_number: str):
        """Get participants for an alarm by incident number."""
        if not _INCIDENT_NUMBER_RE.match(incident_number):
            return jsonify({"error": "Invalid incident number"}), 400

        if not messenger:
            return jsonify({"error": "Messenger not configured"}), 503

        participants = messenger.get_participants(incident_number)
        if participants is None:
            return jsonify({"error": "Failed to fetch participants"}), 500

        return jsonify({"participants": participants})

    @app.route("/api/history")
    def api_history():
        limit: Optional[int] = None
        raw_limit = request.args.get("limit")
        if raw_limit:
            try:
                limit = max(1, min(500, int(raw_limit)))
            except ValueError:
                limit = None

        history_entries = store.history(limit=limit)
        history_payload: List[Dict[str, Any]] = [
            _serialize_history_entry(entry) for entry in history_entries
        ]
        return jsonify({"history": history_payload})

    @app.route("/api/settings", methods=["GET"])
    def api_get_settings():
        """Get current settings."""
        effective_settings = get_settings()
        # Convert activation_groups list to comma-separated string for UI
        groups_str = ",".join(effective_settings.get("activation_groups", []))
        resp = jsonify({
            "fire_department_name": effective_settings["fire_department_name"],
            "default_latitude": effective_settings["default_latitude"],
            "default_longitude": effective_settings["default_longitude"],
            "default_location_name": effective_settings["default_location_name"],
            "activation_groups": groups_str,
        })
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.route("/api/settings", methods=["POST"])
    def api_update_settings():
        """Update settings."""
        # Verify settings password using constant-time comparison
        provided = request.headers.get("X-Settings-Password") or ""
        if not config.settings_password or not hmac.compare_digest(provided, config.settings_password):
            LOGGER.warning("Unauthorized settings update attempt")
            return jsonify({"error": "Unauthorized"}), 401

        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request"}), 400

        # Validate and prepare settings
        updates = {}

        if "fire_department_name" in data:
            updates["fire_department_name"] = str(data["fire_department_name"]).strip()

        # Handle coordinates - require both or neither
        has_lat = "default_latitude" in data and data["default_latitude"]
        has_lon = "default_longitude" in data and data["default_longitude"]

        if has_lat and has_lon:
            try:
                lat = float(data["default_latitude"])
                lon = float(data["default_longitude"])
                # Validate coordinate ranges
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
        elif "default_latitude" in data and not data["default_latitude"] and "default_longitude" in data and not data["default_longitude"]:
            # Allow clearing both coordinates
            updates["default_latitude"] = None
            updates["default_longitude"] = None

        if "default_location_name" in data:
            updates["default_location_name"] = str(data["default_location_name"]).strip() if data["default_location_name"] else None

        if "activation_groups" in data:
            # Parse comma-separated string to list
            groups_str = str(data["activation_groups"]).strip()
            if groups_str:
                groups = [g.strip().upper() for g in groups_str.split(",") if g.strip()]
            else:
                groups = []
            updates["activation_groups"] = groups

        # Update settings
        settings_store.update(updates)
        LOGGER.info("Settings updated: %s", updates)

        resp = jsonify({"status": "ok", "settings": updates})
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.route("/api/route")
    @limiter.limit("30 per minute")
    def api_route():
        """Proxy routing requests to OpenRouteService to keep the ORS API key server-side."""
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

    @app.route("/settings")
    def settings_page() -> str:
        """Settings configuration page."""
        crest_url = url_for("static", filename="img/crest.png")
        effective_settings = get_settings()
        return render_template(
            "settings.html",
            crest_url=crest_url,
            department_name=effective_settings["fire_department_name"],
            app_version=config.app_version,
            app_version_url=config.app_version_url,
            api_key_configured=bool(config.api_key),
        )

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    return app


def main() -> None:
    """Entry point for running the application via ``python -m``."""

    app = create_app()
    app.run(host="0.0.0.0", port=8000)

