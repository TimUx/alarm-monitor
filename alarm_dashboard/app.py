"""Main Flask application exposing the alarm dashboard."""

from __future__ import annotations

import atexit
import concurrent.futures
import hashlib
import hmac
import logging
import os
import re
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from .config import AppConfig, load_config
from .messenger import create_messenger
from .storage import AlarmStore, SettingsStore
from .weather_cache import WeatherCache

LOGGER = logging.getLogger(__name__)

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
atexit.register(_executor.shutdown, wait=False)

_INCIDENT_NUMBER_RE = re.compile(r'^[A-Za-z0-9\-_]{1,50}$')

# Module-level limiter – initialized with app in create_app() via init_app().
# Blueprint route handlers import this to apply per-route limits.
_limiter = Limiter(key_func=get_remote_address)

# ---------------------------------------------------------------------------
# Prometheus-compatible metrics counters (threading-safe)
# ---------------------------------------------------------------------------

_metrics_lock = threading.Lock()
_metrics = {
    "alarms_received": 0,
    "alarms_stored": 0,
    "geocode_errors": 0,
    "weather_errors": 0,
}


def _increment_metric(name: str) -> None:
    """Atomically increment a named metric counter."""
    with _metrics_lock:
        _metrics[name] = _metrics.get(name, 0) + 1


def generate_csrf_token(settings_password: str) -> str:
    """Generate an hourly HMAC-SHA256 CSRF token.

    The token is valid for the current hour window (and accepted for the previous
    hour to handle boundary conditions).
    """
    window = str(int(time.time() // 3600)).encode()
    return hmac.new(settings_password.encode(), window, hashlib.sha256).hexdigest()


def generate_csrf_token_for_hour_offset(settings_password: str, hour_offset: int) -> str:
    """Generate an HMAC-SHA256 CSRF token for a specific hour offset from now.

    Args:
        settings_password: The settings password used as HMAC key.
        hour_offset: Number of hours to offset from current time (e.g. -1 for previous hour).
    """
    window = str(int(time.time() // 3600) + hour_offset).encode()
    return hmac.new(settings_password.encode(), window, hashlib.sha256).hexdigest()


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
        "calendar_urls": stored.get("calendar_urls", config.calendar_urls),
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

    # Asset cache busting helper – appends ?v=<app_version> to static file URLs
    from flask import url_for as _url_for

    def asset_url(filename: str) -> str:
        """Return the URL for a static file with a cache-busting version query string."""
        return _url_for("static", filename=filename) + "?v=" + config.app_version

    app.jinja_env.globals["asset_url"] = asset_url

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

    # Per-app weather cache instance
    weather_cache = WeatherCache()
    app.config["WEATHER_CACHE"] = weather_cache

    # SSE subscriber registry – one threading.Event per connected client
    _subscribers: List[threading.Event] = []
    _subscribers_lock = threading.Lock()
    app.config["SSE_SUBSCRIBERS"] = _subscribers
    app.config["SSE_SUBSCRIBERS_LOCK"] = _subscribers_lock

    # Rate limiter – initialise the module-level limiter with this app instance
    _limiter.init_app(app)
    app.config["LIMITER"] = _limiter

    @app.after_request
    def set_cache_headers(response):
        # Static assets are cache-busted via ?v=<app_version> query strings,
        # so they can be cached normally by the browser.
        if request.path.startswith("/static/"):
            return response
        # All other responses (HTML pages, API endpoints) must never be cached.
        # This is especially important for kiosk displays so that design changes
        # are picked up immediately without a manual cache clear.
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        return response

    # Initialize alarm messenger if configured
    messenger = create_messenger(
        config.messenger_server_url, config.messenger_api_key
    )
    app.config["ALARM_MESSENGER"] = messenger

    # Register blueprints – all route handlers live in routes/api.py and routes/views.py
    from .routes.api import api_bp
    from .routes.views import views_bp
    app.register_blueprint(api_bp)
    app.register_blueprint(views_bp)

    return app


def main() -> None:
    """Entry point for running the application via ``python -m``."""

    app = create_app()
    app.run(host="0.0.0.0", port=8000)

