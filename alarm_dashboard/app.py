"""Main Flask application exposing the alarm dashboard."""

from __future__ import annotations

import atexit
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, render_template, request, url_for

from .config import AppConfig, load_config
from .geocode import geocode_location
from .mail_checker import AlarmMailFetcher
from .parser import parse_alarm
from .storage import AlarmStore
from .weather import fetch_weather

LOGGER = logging.getLogger(__name__)


def create_app(config: Optional[AppConfig] = None) -> Flask:
    """Application factory used by Flask."""

    logging.basicConfig(level=logging.INFO)
    if config is None:
        config = load_config()

    app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"))
    app.config["APP_VERSION"] = config.app_version
    app.config["APP_VERSION_URL"] = config.app_version_url

    if config.history_file:
        persistence_path = Path(config.history_file)
    else:
        persistence_path = Path(app.instance_path) / "alarm_history.json"
        config.history_file = str(persistence_path)

    store = AlarmStore(persistence_path=persistence_path)
    app.config["ALARM_STORE"] = store
    app.config["APP_CONFIG"] = config
    app.config["MAIL_FETCHER"] = None

    def process_email(raw_email: bytes) -> None:
        alarm = parse_alarm(raw_email)
        if alarm is None:
            LOGGER.info("Ignoring email without INCIDENT payload")
            return

        LOGGER.info("Parsed alarm: %s", alarm)
        
        # Check for duplicate based on incident number
        incident_number = alarm.get("incident_number")
        if incident_number and store.has_incident_number(incident_number):
            LOGGER.info(
                "Ignoring duplicate alarm with incident number: %s",
                incident_number,
            )
            return

        activation_filters = config.activation_groups
        if activation_filters:
            dispatch_codes = set()
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
                    "Ignoring alarm without configured groups: filters=%s, codes=%s",
                    activation_filters,
                    sorted(dispatch_codes),
                )
                return
        location = alarm.get("location")
        coordinates = None
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
            except Exception as exc:  # pragma: no cover - best effort
                LOGGER.warning("Failed to geocode location %s: %s", location, exc)

        if coordinates:
            try:
                weather = fetch_weather(
                    config.weather_base_url,
                    config.weather_params,
                    float(coordinates["lat"]),
                    float(coordinates["lon"]),
                )
            except Exception as exc:  # pragma: no cover - best effort
                LOGGER.warning("Failed to fetch weather: %s", exc)
        alarm_payload: Dict[str, Any] = {
            "alarm": alarm,
            "coordinates": coordinates,
            "weather": weather,
        }
        store.update(alarm_payload)

    fetcher: Optional[AlarmMailFetcher] = None

    def _ensure_background_fetcher_started() -> None:
        """Ensure the background mail fetcher reference is registered."""

        return None

    if config.mail is not None:
        fetcher = AlarmMailFetcher(
            config=config.mail,
            callback=process_email,
            poll_interval=config.poll_interval,
        )

        try:
            fetcher.start()
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.error("Failed to start mail fetcher: %s", exc)
            fetcher = None
        else:

            app.config["MAIL_FETCHER"] = fetcher

            def _ensure_background_fetcher_started() -> None:
                """Ensure the fetcher remains available to the application."""

                nonlocal fetcher
                if fetcher is None:
                    return
                if app.config.get("MAIL_FETCHER") is not fetcher:
                    app.config["MAIL_FETCHER"] = fetcher

            def _stop_background_fetcher() -> None:
                nonlocal fetcher
                if fetcher is not None:
                    fetcher.stop()
                    fetcher = None
                    app.config["MAIL_FETCHER"] = None

            app.config["MAIL_FETCHER_CLEANUP"] = _stop_background_fetcher

    # ``before_first_request`` was removed in Flask 3.0.  Older releases, however,
    # still rely on it, so we probe the available lifecycle hooks in a
    # compatibility-friendly way without assuming the attribute exists.
    for hook_name in ("before_serving", "before_request"):
        try:
            hook = getattr(app, hook_name)
        except AttributeError:
            continue
        if not callable(hook):
            continue

        hook(_ensure_background_fetcher_started)
        if hook_name != "before_serving":
            # Legacy Flask versions do not provide ``before_serving`` so we start the
            # fetcher immediately instead of waiting for the first HTTP request.
            _ensure_background_fetcher_started()
        break
    else:  # Fallback if Flask does not expose lifecycle hooks
        _ensure_background_fetcher_started()

    @app.route("/")
    def dashboard() -> str:
        crest_url = url_for("static", filename="img/crest.png")
        return render_template(
            "dashboard.html",
            crest_url=crest_url,
            department_name=config.fire_department_name,
            display_duration_minutes=config.display_duration_minutes,
            app_version=config.app_version,
            app_version_url=config.app_version_url,
        )

    @app.route("/navigation")
    def navigation_page() -> str:
        crest_url = url_for("static", filename="img/crest.png")
        return render_template(
            "navigation.html",
            crest_url=crest_url,
            department_name=config.fire_department_name,
            default_latitude=config.default_latitude,
            default_longitude=config.default_longitude,
            default_location_name=config.default_location_name,
            ors_api_key=config.ors_api_key,
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
        return render_template(
            "history.html",
            entries=decorated,
            crest_url=crest_url,
            department_name=config.fire_department_name,
            app_version=config.app_version,
            app_version_url=config.app_version_url,
        )

    @app.route("/mobile")
    def mobile_dashboard() -> str:
        crest_url = url_for("static", filename="img/crest.png")
        return render_template(
            "mobile.html",
            crest_url=crest_url,
            department_name=config.fire_department_name,
            app_version=config.app_version,
            app_version_url=config.app_version_url,
        )

    def _serialize_history_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
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
            "description": alarm.get("description"),
            "groups": alarm.get("groups"),
            "aao_groups": alarm.get("aao_groups"),
            "remark": alarm.get("remark"),
        }

    def _build_idle_response(last_alarm: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        weather = None
        if (
            config.default_latitude is not None
            and config.default_longitude is not None
        ):
            try:
                weather = fetch_weather(
                    config.weather_base_url,
                    config.weather_params,
                    config.default_latitude,
                    config.default_longitude,
                )
            except Exception as exc:  # pragma: no cover - best effort
                LOGGER.warning("Failed to fetch idle weather: %s", exc)
        last_alarm_entry: Optional[Dict[str, Any]] = None
        if last_alarm:
            last_alarm_entry = _serialize_history_entry(last_alarm)

        return {
            "mode": "idle",
            "alarm": None,
            "weather": weather,
            "location": config.default_location_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "last_alarm": last_alarm_entry,
        }

    @app.route("/api/alarm")
    def api_alarm():
        alarm_payload = store.latest()
        if alarm_payload is None:
            return jsonify(_build_idle_response(None))

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
            return jsonify(_build_idle_response(alarm_payload))

        response: Dict[str, Any] = {
            "mode": "alarm",
            "alarm": alarm_payload.get("alarm"),
            "coordinates": alarm_payload.get("coordinates"),
            "weather": alarm_payload.get("weather"),
            "received_at": (
                received_at.isoformat() if isinstance(received_at, datetime) else None
            ),
        }
        return jsonify(response)

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

    @app.route("/api/mobile/alarm")
    def api_mobile_alarm():
        return api_alarm()

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    return app


def main() -> None:
    """Entry point for running the application via ``python -m``."""

    app = create_app()
    app.run(host="0.0.0.0", port=8000)


if __name__ == "__main__":  # pragma: no cover
    main()
